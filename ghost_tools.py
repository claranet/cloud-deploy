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

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))

with open(os.path.dirname(os.path.realpath(__file__)) + '/config.yml', 'r') as conf_file:
    config = yaml.load(conf_file)

def render_stage2(config, s3_region):
    """
    Renders the stage2 script that is the second step of EC2 instance bootstrapping through userdata (stage1).

    The 'config' dict should contain the following parameters:
    * 'bucket_s3': name of the Ghost S3 bucket (required)
    * 'ghost_root_path': path to the root of the Ghost installation (required)
    * 'max_deploy_history': maximum number of deployments to preserve after a deployment (optional).

    If 'max_deploy_history' is not defined in the 'config' dict, the render_stage2() function uses 3 as the default value:

    >>> config = {'bucket_s3': 'my-s3-bucket', 'ghost_root_path': '.'}
    >>> stage2 = render_stage2(config, 'eu-west-1')
    >>> stage2[stage2.find('S3_BUCKET'):stage2.find('\\n', stage2.find('S3_BUCKET')+1)]
    u'S3_BUCKET=my-s3-bucket'
    >>> stage2[stage2.find('S3_REGION'):stage2.find('\\n', stage2.find('S3_REGION')+1)]
    u'S3_REGION=eu-west-1'
    >>> stage2[stage2.find('MAX_DEPLOY_HISTORY'):stage2.find('\\n', stage2.find('MAX_DEPLOY_HISTORY')+1)]
    u'MAX_DEPLOY_HISTORY="3"'

    This can be overridden by defining the 'max_deploy_history' configuration setting:

    >>> config = {'bucket_s3': 'my-s3-bucket', 'ghost_root_path': '.', 'max_deploy_history': 1}
    >>> stage2 = render_stage2(config, 'ap-northeast-1')
    >>> stage2[stage2.find('S3_BUCKET'):stage2.find('\\n', stage2.find('S3_BUCKET')+1)]
    u'S3_BUCKET=my-s3-bucket'
    >>> stage2[stage2.find('S3_REGION'):stage2.find('\\n', stage2.find('S3_REGION')+1)]
    u'S3_REGION=ap-northeast-1'
    >>> stage2[stage2.find('MAX_DEPLOY_HISTORY'):stage2.find('\\n', stage2.find('MAX_DEPLOY_HISTORY')+1)]
    u'MAX_DEPLOY_HISTORY="1"'
    """
    bucket_s3 = config['bucket_s3']
    ghost_root_path = config['ghost_root_path']
    max_deploy_history = config.get('max_deploy_history', 3)

    jinja_templates_path='%s/scripts' % ghost_root_path
    if(os.path.exists('%s/stage2' % jinja_templates_path)):
        loader=FileSystemLoader(jinja_templates_path)
        jinja_env = Environment(loader=loader)
        template = jinja_env.get_template('stage2')
        return template.render(bucket_s3=bucket_s3, max_deploy_history=max_deploy_history, bucket_region=s3_region)
    return None

def refresh_stage2(region, config):
    """
    Will update the second phase of bootstrap script on S3
    """
    conn = boto.s3.connect_to_region(region)
    bucket_s3 = config['bucket_s3']
    bucket = conn.get_bucket(bucket_s3)
    stage2 = render_stage2(config, region)
    if stage2 is not None:
        key = bucket.new_key("/ghost/stage2")
        key.set_contents_from_string(stage2)
        key.close()
    else:
        bucket.delete_key("/ghost/stage2")


class GCallException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def gcall(args, cmd_description, log_fd, dry_run=False, env=None):
    log(cmd_description, log_fd)
    log("CMD: {0}".format(args), log_fd)
    if not dry_run:
        ret = call(args, stdout=log_fd, stderr=log_fd, shell=True, env=env)
        if (ret != 0):
            raise GCallException("ERROR: %s" % cmd_description)

def find_ec2_pending_instances(ghost_app, ghost_env, ghost_role, region, as_group):
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

def deploy_module_on_hosts(module, fabric_execution_strategy, app, config, log_file):
    app_name = app['name']
    app_env = app['env']
    app_role = app['role']
    app_region = app['region']

    bucket_region = config.get('bucket_region', app_region)

    key_filename = config.get('key_path', '')
    if isinstance(key_filename, dict):
        key_filename = key_filename[app_region]

    # Retrieve autoscaling infos, if any
    as_conn = boto.ec2.autoscale.connect_to_region(app_region)
    as_group, as_group_processes_to_suspend = get_autoscaling_group_and_processes_to_suspend(as_conn, app, log_file)

    try:
        # Suspend autoscaling
        suspend_autoscaling_group_processes(as_conn, as_group, as_group_processes_to_suspend, log_file)

        # Wait for pending instances to become ready
        while True:
            pending_instances = find_ec2_pending_instances(app_name, app_env, app_role, app_region, as_group)
            if not pending_instances:
                break

            log("INFO: waiting 10s for {} instance(s) to become running before proceeding with deployment: {}".format(len(pending_instances), pending_instances), log_file)
            time.sleep(10)

        running_instances = find_ec2_running_instances(app_name, app_env, app_role, app_region)

        if len(running_instances) > 0:
            hosts_list = [host['private_ip_address'] for host in running_instances]
            app_ssh_username = app['build_infos']['ssh_username']
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

            log("Updating current instances in {}: {}".format(fabric_execution_strategy, running_instances), log_file)
            fab_execute(task, module, app_ssh_username, key_filename, stage2, log_file, hosts=hosts_list)
        else:
            raise GCallException("No instance found in region {region} with tags app:{app}, env:{env}, role:{role}".format(region=app_region,
                                                                                                                           app=app_name,
                                                                                                                           env=app_env,
                                                                                                                           role=app_role))
    finally:
        # Resume autoscaling
        resume_autoscaling_group_processes(as_conn, as_group, as_group_processes_to_suspend, log_file)

def log(message, fd):
    fd.write("{timestamp}: {message}\n".format(timestamp=datetime.now().strftime("%Y/%m/%d %H:%M:%S GMT"), message=message))

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

def purge_launch_configuration(app, retention):
    conn_as = boto.ec2.autoscale.connect_to_region(app['region'])
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

def update_auto_scale(app, launch_config, log_file, update_as_params=False):
    conn = boto.ec2.autoscale.connect_to_region(app['region'])
    as_group = conn.get_all_groups(names=[app['autoscale']['name']])[0]
    setattr(as_group, 'launch_config_name', launch_config.name)
    if update_as_params:
        setattr(as_group, 'desired_capacity', app['autoscale']['current'])
        setattr(as_group, 'min_size', app['autoscale']['min'])
        setattr(as_group, 'max_size', app['autoscale']['max'])
    as_group.update()
    log("Autoscaling group [{0}] updated.".format(app['autoscale']['name']), log_file)

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

def get_rq_name_from_app(app):
    """
    Returns an RQ name for a given ghost app.

    The default strategy is to use one worker per app:

    >>> config['rq_worker_strategy'] = None
    >>> get_rq_name_from_app({'env': 'prod', 'name': 'App1', 'role': 'webfront'})
    'prod:App1:webfront'

    >>> config['rq_worker_strategy'] = 'one_worker_per_app'
    >>> get_rq_name_from_app({'env': 'prod', 'name': 'App1', 'role': 'webfront'})
    'prod:App1:webfront'

    An alternative strategy is to use one worker per env:

    >>> config['rq_worker_strategy'] = 'one_worker_per_env'
    >>> get_rq_name_from_app({'env': 'prod', 'name': 'App1', 'role': 'webfront'})
    'prod:*:*'

    Another alternative strategy is to use a single worker for all:

    >>> config['rq_worker_strategy'] = 'one_worker_for_all'
    >>> get_rq_name_from_app({'env': 'prod', 'name': 'App1', 'role': 'webfront'})
    'default:*:*'
    """
    rq_worker_strategy = config.get('rq_worker_strategy', 'one_worker_per_app')
    env=app['env']
    name=app['name']
    role=app['role']

    if rq_worker_strategy == 'one_worker_per_env':
        name = role = '*'

    if rq_worker_strategy == 'one_worker_for_all':
        name = role = '*'
        env = 'default'

    return '{env}:{name}:{role}'.format(env=env, name=name, role=role)

def get_app_from_rq_name(name):
    """
    Returns an app's env, name, role for a given RQ name

    >>> sorted(get_app_from_rq_name('prod:App1:webfront').items())
    [('env', 'prod'), ('name', 'App1'), ('role', 'webfront')]
    """
    parts = name.split(':')
    return {'env': parts[0], 'name': parts[1], 'role': parts[2]}

def clean_local_module_workspace(app_path, all_app_modules_list, log_file):
    """
    Walk through app_path directory and check if module workspace should be cleaned.
    """

    log('Cleaning old module workspaces', log_file)
    for mod_dir in os.listdir(app_path):
        if not mod_dir in all_app_modules_list:
            gcall('rm -rf {p}'.format(p=os.path.join(app_path, mod_dir)), 'Removing deleted module : %s' % mod_dir, log_file)

def get_app_module_name_list(modules):
    """
    Returns the list of module name from a Ghost App
    """
    return [app_module['name'] for app_module in modules if 'name' in app_module]
