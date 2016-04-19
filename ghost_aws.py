from datetime import datetime
import os
from subprocess import call
import time
import yaml
from copy import copy

from fabric.api import execute as fab_execute
from fabfile import deploy
from jinja2 import Environment, FileSystemLoader

import boto.ec2.autoscale
import boto.ec2.blockdevicemapping
import boto.s3
from libs.safe_deployment import SafeDeployment

from ghost_log import log

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))

with open(os.path.dirname(os.path.realpath(__file__)) + '/config.yml', 'r') as conf_file:
    config = yaml.load(conf_file)

def find_ec2_pending_instances(ghost_app, ghost_env, ghost_role, region, as_group):
    """ Return a list of dict info only for the instances in pending state.

        :param  ghost_app  string: The value for the instance tag "app".
        :param  ghost_env  string: The value for the instance tag "env".
        :param  ghost_role  string: The value for the instance tag "role".
        :param  region  string: The AWS region where the instances are located.
        :return list of dict(ex: [{'id': instance_idXXX, 'private_ip_address': XXX_XXX_XXX_XXX},{...}])
    """
    conn_as = boto.ec2.autoscale.connect_to_region(region)
    conn = boto.ec2.connect_to_region(region)

    # Retrieve pending instances
    pending_instance_filters = {"tag:env": ghost_env, "tag:role": ghost_role, "tag:app": ghost_app, "instance-state-name": "pending"}
    pending_instances = conn.get_only_instances(filters=pending_instance_filters)
    pending_instances_ids = [instance.id for instance in pending_instances]

    autoscale_instances = []
    if as_group:
        autoscale_instances = conn_as.get_all_groups(names=[as_group])[0].instances

    for autoscale_instance in autoscale_instances:
        # Instances in autoscale "Pending" state may not have their tags set yet
        if not autoscale_instance.instance_id in pending_instances_ids and autoscale_instance.lifecycle_state in ['Pending', 'Pending:Wait', 'Pending:Proceed']:
            pending_instances.append(conn.get_only_instances(instance_ids=[autoscale_instance.instance_id])[0])

    hosts = []
    for instance in pending_instances:
        hosts.append({'id': instance.id, 'private_ip_address': instance.private_ip_address})

    return hosts

def find_ec2_running_instances(ghost_app, ghost_env, ghost_role, region):
    """ Return a list of dict info only for the running instances.

        :param  ghost_app  string: The value for the instance tag "app".
        :param  ghost_env  string: The value for the instance tag "env".
        :param  ghost_role  string: The value for the instance tag "role".
        :param  region  string: The AWS region where the instances are located.
        :return list of dict(ex: [{'id': instance_idXXX, 'private_ip_address': XXX_XXX_XXX_XXX},{...}])
    """
    conn_as = boto.ec2.autoscale.connect_to_region(region)
    conn = boto.ec2.connect_to_region(region)

    # Retrieve running instances
    running_instance_filters = {"tag:env": ghost_env, "tag:role": ghost_role, "tag:app": ghost_app, "instance-state-name": "running"}
    running_instances = conn.get_only_instances(filters=running_instance_filters)

    hosts = []
    for instance in running_instances:
        # Instances in autoscale "Terminating:*" states are still "running" but no longer in the Load Balancer
        autoscale_instances = conn_as.get_all_autoscaling_instances(instance_ids=[instance.id])
        if not autoscale_instances or not autoscale_instances[0].lifecycle_state in ['Terminating', 'Terminating:Wait', 'Terminating:Proceed']:
            hosts.append({'id': instance.id, 'private_ip_address': instance.private_ip_address})

    return hosts

def get_autoscaling_group_and_processes_to_suspend(as_conn, app, log_file):
    if 'autoscale' in app.keys() and 'name' in app['autoscale'].keys() and app['autoscale']['name']:
        as_name = app['autoscale']['name']
        as_list = as_conn.get_all_groups(names=[as_name])

        if len(as_list) == 1:
            as_group = as_list[0].name
            log("INFO: Auto-scaling group {0} found".format(as_name), log_file)

            # Determine if the auto-scaling Launch and/or Terminate processes should be suspended (i.e. they are already suspended and should remain as is)
            as_processes_to_suspend = {'Launch': None, 'Terminate': None}
            for suspended_process in as_list[0].suspended_processes:
                if suspended_process.process_name in ['Launch', 'Terminate']:
                    del as_processes_to_suspend[suspended_process.process_name]
                    log("INFO: Auto-scaling group {0} {1} process is already suspended".format(as_name, suspended_process.process_name), log_file)

            return as_group, as_processes_to_suspend.keys()
        else:
            log("WARNING: Auto-scaling group {0} not found".format(as_name), log_file)
            all_as = as_conn.get_all_groups()
            if len(all_as) > 0:
                for ec2_as in all_as:
                    log("WARNING:    Auto-scaling group found: {0}".format(ec2_as.name), log_file)
            else:
                log("WARNING: No auto-scaling group found", log_file)
    return None, None

def suspend_autoscaling_group_processes(as_conn, as_group, as_group_processes_to_suspend, log_file):
    if as_group and as_group_processes_to_suspend:
        log("Suspending auto-scaling group processes {0}".format(as_group_processes_to_suspend), log_file)
        as_conn.suspend_processes(as_group, as_group_processes_to_suspend)

def resume_autoscaling_group_processes(as_conn, as_group, as_group_processes_to_suspend, log_file):
    if as_group and as_group_processes_to_suspend:
        log("Resuming auto-scaling group processes {0}".format(as_group_processes_to_suspend), log_file)
        as_conn.resume_processes(as_group, as_group_processes_to_suspend)

def deploy_module_on_hosts(module, fabric_execution_strategy, app, config, log_file, **kwargs):
    """ Prepare the deployment process on instances.

        :param  module                     dict: Ghost object wich describe the module parameters.
        :param  app                        dict: Ghost object which describe the application parameters.
        :param  fabric_execution_strategy  string: Deployment strategy(serial or parrallel).
        :param  config                     dict: The worker configuration.
        :param  log_file:                  object for logging.
        :param   **kwargs: optional arguments in dict format.
                Example: {'safe-deployment': {'load_balancer_type': 'elb', 'type': '1by1/25%/50%',
                        'wait_before_deploy': 30, 'wait_after_deploy': 60}}
                         {'safe-deployment': {'load_balancer_type': 'ha', 'type': '1by1/25%/50%',
                        'app_id_ha': 'xxxx', 'ha_backend':xxx, 'wait_before_deploy': 30, 'wait_after_deploy': 60}}
    """
    app_name = app['name']
    app_env = app['env']
    app_role = app['role']
    app_region = app['region']

    # Retrieve autoscaling infos, if any
    as_conn = boto.ec2.autoscale.connect_to_region(app_region)
    as_group, as_group_processes_to_suspend = get_autoscaling_group_and_processes_to_suspend(as_conn, app, log_file)
    try:
        suspend_autoscaling_group_processes(as_conn, as_group, as_group_processes_to_suspend, log_file)
        # Wait for pending instances to become ready
        while True:
            pending_instances = find_ec2_pending_instances(app_name, app_env, app_role, app_region, as_group)
            if not pending_instances:
                break
            log("INFO: waiting 10s for {} instance(s) to become running before proceeding with deployment: {}".format(len(pending_instances), pending_instances), log_file)
            time.sleep(10)
        running_instances = find_ec2_running_instances(app_name, app_env, app_role, app_region)
        if running_instances:
            hosts_list = [host['private_ip_address'] for host in running_instances]
            if 'safe-deployment' in kwargs:
                safedeploy = SafeDeployment(app, module, hosts_list, log_file, kwargs['safe-deployment'], fabric_execution_strategy, as_group, app_region)
                safedeploy.safe_manager()
            else:
                launch_deploy(app, module, hosts_list, fabric_execution_strategy, log_file)
        else:
            raise GCallException("No instance found in region {region} with tags app:{app}, env:{env}, role:{role}".format(region=app_region,
                                                                                                                           app=app_name,
                                                                                                                           env=app_env,
                                                                                                                           role=app_role))
    finally:
        resume_autoscaling_group_processes(as_conn, as_group, as_group_processes_to_suspend, log_file)


def launch_deploy(app, module, hosts_list, fabric_execution_strategy, log_file):
    """ Launch fabric tasks on remote hosts.

        :param  app:          dict: Ghost object which describe the application parameters.
        :param  fabric_execution_strategy  string: Deployment strategy(serial or parrallel).
        :param  module:       dict: Ghost object which describe the module parameters.
        :param  hosts_list:   list: Instances private IP.
        :param  log_file:     object for logging.
    """
    key_filename = config.get('key_path', '')
    if isinstance(key_filename, dict):
        key_filename = key_filename[app['region']]
    app_ssh_username = app['build_infos']['ssh_username']
    bucket_region = config.get('bucket_region', app['region'])
    stage2 = render_stage2(config, bucket_region)
    if fabric_execution_strategy not in ['serial', 'parallel']:
        fabric_execution_strategy = config.get('fabric_execution_strategy', 'serial')
        # Clone the deploy task function to avoid modifying the original shared instance
    task = copy(deploy)
    if fabric_execution_strategy == 'parallel':
        setattr(task, 'serial', False)
        setattr(task, 'parallel', True)
    else:
        setattr(task, 'serial', True)
        setattr(task, 'parallel', False)
    log("Updating current instances in {}: {}".format(fabric_execution_strategy, hosts_list), log_file)
    fab_execute(task, module, app_ssh_username, key_filename, stage2, log_file, hosts=hosts_list)

def create_launch_config(app, userdata, ami_id):
    d = time.strftime('%d%m%Y-%H%M',time.localtime())
    launch_config_name = "launchconfig.{0}.{1}.{2}.{3}.{4}".format(app['env'], app['region'], app['role'], app['name'], d)
    conn_as = boto.ec2.autoscale.connect_to_region(app['region'])
    if 'root_block_device' in app['environment_infos']:
        bdm = create_block_device(app['environment_infos']['root_block_device'])
    else:
        bdm = create_block_device()
    launch_config = boto.ec2.autoscale.LaunchConfiguration(name=launch_config_name,
        image_id=ami_id, key_name=app['environment_infos']['key_name'],
        security_groups=app['environment_infos']['security_groups'],
        user_data=userdata, instance_type=app['instance_type'], kernel_id=None,
        ramdisk_id=None, block_device_mappings=[bdm],
        instance_monitoring=False, spot_price=None,
        instance_profile_name=app['environment_infos']['instance_profile'], ebs_optimized=False,
        associate_public_ip_address=True, volume_type=None,
        delete_on_termination=True, iops=None,
        classic_link_vpc_id=None, classic_link_vpc_security_groups=None)
    conn_as.create_launch_configuration(launch_config)
    return launch_config

def generate_userdata(bucket_s3, s3_region, root_ghost_path):
    jinja_templates_path='%s/scripts' % root_ghost_path
    if(os.path.exists('%s/stage1' % jinja_templates_path)):
        loader=FileSystemLoader(jinja_templates_path)
        jinja_env = Environment(loader=loader)
        template = jinja_env.get_template('stage1')
        userdata = template.render(bucket_s3=bucket_s3, bucket_region=s3_region)
        return userdata
    else:
        return ""

def check_autoscale_exists(as_name, region):
    conn_as = boto.ec2.autoscale.connect_to_region(region)
    autoscale = conn_as.get_all_groups(names=[as_name])
    if autoscale:
        return True
    else:
        return False

def purge_launch_configuration(app):
    conn_as = boto.ec2.autoscale.connect_to_region(app['region'])
    retention = 2
    launchconfigs = []
    lcs = conn_as.get_all_launch_configurations()

    launchconfig_format = "launchconfig.{0}.{1}.{2}.{3}.".format(app['env'], app['region'], app['role'], app['name'])

    for lc in lcs:
        if launchconfig_format in lc.name:
            launchconfigs.append(lc)

    if launchconfigs and len(launchconfigs) > retention:
        launchconfigs.sort(key=lambda lc: lc.created_time, reverse=True)
        i = 0
        while i < retention:
            launchconfigs.pop(0)
            i += 1

        for lc in launchconfigs:
            conn_as.delete_launch_configuration(lc.name)

    #Check if the purge works : current_version and current_version -1 are not removed.
    lcs = []
    launchconfigs = []
    lcs = conn_as.get_all_launch_configurations()
    for lc in lcs:
        if launchconfig_format in lc.name:
            launchconfigs.append(lc)
    if len(launchconfigs) <= 2:
        return True
    else:
        return False

def create_block_device(rbd={}):
    dev_sda1 = boto.ec2.blockdevicemapping.EBSBlockDeviceType(delete_on_termination=True)
    if 'type' in rbd:
        dev_sda1.volume_type = rbd['type']
    else:
        dev_sda1.volume_type = "gp2"
    if 'size' in rbd:
        dev_sda1.size = rbd['size']
    else:
        rbd['size'] = 10
        dev_sda1.size = rbd['size']
    bdm = boto.ec2.blockdevicemapping.BlockDeviceMapping()
    if 'name' in rbd:
        bdm[rbd['name']] = dev_sda1
    else:
        rbd['name'] = "/dev/xvda"
        bdm[rbd['name']] = dev_sda1
    return bdm
