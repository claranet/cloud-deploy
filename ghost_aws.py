import os
import time
import yaml

from jinja2 import Environment, FileSystemLoader

from boto.ec2.autoscale import Tag

from libs.safe_deployment import SafeDeployment
from libs.deploy import launch_deploy
from libs.ec2 import find_ec2_pending_instances, find_ec2_running_instances

from ghost_tools import GCallException
from ghost_log import log

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))

with open(os.path.dirname(os.path.realpath(__file__)) + '/config.yml', 'r') as conf_file:
    config = yaml.load(conf_file)

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

def deploy_module_on_hosts(cloud_connection, module, fabric_execution_strategy, app, config, log_file, safe_deployment_strategy):
    """ Prepare the deployment process on instances.

        :param  cloud_connection           object: AWS Provider
        :param  module                     dict: Ghost object wich describe the module parameters.
        :param  app                        dict: Ghost object which describe the application parameters.
        :param  fabric_execution_strategy  string: Deployment strategy(serial or parrallel).
        :param  safe_deployment_strategy   string: Safe Deployment strategy(1by1-1/3-25%-50%).
        :param  config                     dict: The worker configuration.
        :param  log_file:                  object for logging.
    """
    app_name = app['name']
    app_env = app['env']
    app_role = app['role']
    app_region = app['region']
    app_blue_green = app.get('blue_green', None)
    if app_blue_green:
        app_color = app_blue_green.get('color', None)
    else:
        app_color = None

    # Retrieve autoscaling infos, if any
    as_conn = cloud_connection.get_connection(app_region, ["ec2", "autoscale"])
    as_group, as_group_processes_to_suspend = get_autoscaling_group_and_processes_to_suspend(as_conn, app, log_file)
    try:
        # Suspend autoscaling
        suspend_autoscaling_group_processes(as_conn, as_group, as_group_processes_to_suspend, log_file)
        # Wait for pending instances to become ready
        while True:
            pending_instances = find_ec2_pending_instances(cloud_connection, app_name, app_env, app_role, app_region, as_group, ghost_color=app_color)
            if not pending_instances:
                break
            log("INFO: waiting 10s for {} instance(s) to become running before proceeding with deployment: {}".format(len(pending_instances), pending_instances), log_file)
            time.sleep(10)
        running_instances = find_ec2_running_instances(cloud_connection, app_name, app_env, app_role, app_region, ghost_color=app_color)
        if running_instances:
            hosts_list = [host['private_ip_address'] for host in running_instances]
            if safe_deployment_strategy:
                safedeploy = SafeDeployment(cloud_connection, app, module, running_instances, log_file, app['safe-deployment'], fabric_execution_strategy, as_group)
                safedeploy.safe_manager(safe_deployment_strategy)
            else:
                launch_deploy(app, module, hosts_list, fabric_execution_strategy, log_file)
        else:
            raise GCallException("No instance found in region {region} with tags app:{app}, env:{env}, role:{role}{if_color}{color}".format(region=app_region,
                                                                                                                                            app=app_name,
                                                                                                                                            env=app_env,
                                                                                                                                            role=app_role,
                                                                                                                                            if_color=', color:' if app_color else '',
                                                                                                                                            color=app_color if app_color else ''))
    finally:
        resume_autoscaling_group_processes(as_conn, as_group, as_group_processes_to_suspend, log_file)

def create_launch_config(cloud_connection, app, userdata, ami_id):
    d = time.strftime('%d%m%Y-%H%M',time.localtime())
    blue_green = app.get('blue_green', None)
    color = None
    if blue_green:
        color = app['blue_green'].get('color', 'None')

    launch_config_name = "launchconfig.{0}.{1}.{2}.{3}{if_color}{color}.{4}".format(app['env'],
                                                                                    app['region'],
                                                                                    app['role'],
                                                                                    app['name'],
                                                                                    d,
                                                                                    if_color='.' if color else '',
                                                                                    color=color if color else '')
    conn_as = cloud_connection.get_connection(app['region'], ["ec2", "autoscale"])
    if 'root_block_device' in app['environment_infos']:
        bdm = create_block_device(cloud_connection, app['region'], app['environment_infos']['root_block_device'])
    else:
        bdm = create_block_device(cloud_connection, app['region'])
    launch_config = cloud_connection.launch_service(
        ["ec2", "autoscale", "LaunchConfiguration"],
        connection=conn_as,
        name=launch_config_name,
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

def check_autoscale_exists(cloud_connection, as_name, region):
    conn_as = cloud_connection.get_connection(region, ["ec2", "autoscale"])
    autoscale = conn_as.get_all_groups(names=[as_name])
    if autoscale:
        return True
    else:
        return False

def purge_launch_configuration(cloud_connection, app, retention):
    conn_as = cloud_connection.get_connection(app['region'], ["ec2", "autoscale"])
    launchconfigs = []
    lcs = conn_as.get_all_launch_configurations()
    blue_green = app.get('blue_green', None)
    color = None
    if blue_green:
        color = app['blue_green'].get('color', 'None')

    launchconfig_format = "launchconfig.{0}.{1}.{2}.{3}{if_color}{color}.".format(app['env'],
                                                                                  app['region'],
                                                                                  app['role'],
                                                                                  app['name'],
                                                                                  if_color='.' if color else '',
                                                                                  color=color if color else '')

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
    if len(launchconfigs) <= retention:
        return True
    else:
        return False

def update_auto_scale(cloud_connection, app, launch_config, log_file, update_as_params=False):
    """ Update the AutoScaling parameters.

        :param  cloud_connection
        :param  app               dict  The app config define in Ghost.
        :param  launch_config     boto obj  The new launch configuration.
        :param  log_file          log file obj
        :param  update_as_params  Bool  If set to True the desired_capacity/min_size/max_size/subnets will be updated
        :return   None
    """
    conn = cloud_connection.get_connection(app ['region'], ["ec2", "autoscale"])
    connvpc = cloud_connection.get_connection(app['region'], ["vpc"])
    az = [i.availability_zone for i in connvpc.get_all_subnets(subnet_ids=app['environment_infos']['subnet_ids'])]
    as_group = conn.get_all_groups(names=[app['autoscale']['name']])[0]
    setattr(as_group, 'launch_config_name', launch_config.name)
    if update_as_params:
        setattr(as_group, 'desired_capacity', app['autoscale']['current'])
        setattr(as_group, 'min_size', app['autoscale']['min'])
        setattr(as_group, 'max_size', app['autoscale']['max'])
        setattr(as_group, 'availability_zones', az)
        setattr(as_group, 'vpc_zone_identifier', ','.join(app['environment_infos']['subnet_ids']))
    as_group.update()
    log("Autoscaling group [{0}] updated.".format(app['autoscale']['name']), log_file)
    if update_as_params:
        conn.create_or_update_tags(get_auto_scale_tags(cloud_connection, as_group, app, log_file))
        log("Autoscaling tags [{0}] updated.".format(app['autoscale']['name']), log_file)

def get_auto_scale_tags(cloud_connection, as_group, app, log_file):
    """
    Get existing tags and set specific tags needed by Ghost
    """
    as_tags = {}
    for tag in as_group.tags:
        as_tags[tag.key] = tag

    log("[{0}] has those tags enabled: {1}".format(app['autoscale']['name'], ", ".join(as_tags.keys())), log_file)
    as_tags['app_id'] = Tag(key='app_id',
                         value=app['_id'],
                         propagate_at_launch=True,
                         resource_id=app['autoscale']['name'])
    as_tags['app'] = Tag(key='app',
                         value=app['name'],
                         propagate_at_launch=True,
                         resource_id=app['autoscale']['name'])
    as_tags['env'] = Tag(key='env',
                         value=app['env'],
                         propagate_at_launch=True,
                         resource_id=app['autoscale']['name'])
    as_tags['role'] = Tag(key='role',
                          value=app['role'],
                          propagate_at_launch=True,
                          resource_id=app['autoscale']['name'])
    if app.get('blue_green') and app['blue_green'].get('color'):
        as_tags['color'] = Tag(key='color',
                               value=app['blue_green']['color'],
                               propagate_at_launch=True,
                               resource_id=app['autoscale']['name'])
    log("[{0}] will be updated with: {1}".format(app['autoscale']['name'], ", ".join(as_tags.keys())), log_file)
    return as_tags.values()

def create_block_device(cloud_connection, region, rbd={}):
    conn = cloud_connection.get_connection(region, ["ec2"])
    dev_sda1 = cloud_connection.launch_service(
        ["ec2", "blockdevicemapping", "EBSBlockDeviceType"],
        connection=conn,
        delete_on_termination=True
    )
    if 'type' in rbd:
        dev_sda1.volume_type = rbd['type']
    else:
        dev_sda1.volume_type = "gp2"
    if 'size' in rbd:
        dev_sda1.size = rbd['size']
    else:
        rbd['size'] = 10
        dev_sda1.size = rbd['size']
    bdm = cloud_connection.launch_service(
        ["ec2", "blockdevicemapping", "BlockDeviceMapping"],
        connection=conn
    )
    if 'name' in rbd:
        bdm[rbd['name']] = dev_sda1
    else:
        rbd['name'] = "/dev/xvda"
        bdm[rbd['name']] = dev_sda1
    return bdm
