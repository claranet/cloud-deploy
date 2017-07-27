import os
import os.path
import time
import yaml
from botocore.exceptions import ClientError

from libs.ec2 import create_block_device, generate_userdata
from libs.autoscaling import get_autoscaling_group_object
from libs.blue_green import get_blue_green_from_app

from ghost_tools import boolify
from ghost_log import log

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))

with open(os.path.dirname(os.path.realpath(__file__)) + '/config.yml', 'r') as conf_file:
    config = yaml.load(conf_file)


def dict_to_aws_tags(d):
    """
    Transforms a python dict {'a': 'b', 'c': 'd'} to the
    aws tags format [{'Key': 'a', 'Value': 'b'}, {'Key': 'c', 'Value': 'd'}]
    Only needed for boto3 api calls
    :param d: dict: the dict to transform
    :return: list: the tags in aws format

    >>> from pprint import pprint
    >>> pprint(sorted(dict_to_aws_tags({'a': 'b', 'c': 'd'}), key=lambda d: d['Key']))
    [{'Key': 'a', 'Value': 'b'}, {'Key': 'c', 'Value': 'd'}]
    """
    return [{'Key': k, 'Value': v} for k, v in d.items()]


def aws_tags_to_dict(t):
    """
    Transforms a list of aws tags like [{'Key': 'a', 'Value': 'b'}, {'Key': 'c', 'Value': 'd'}]
    in a python dict {'a': 'b', 'c': 'd'}
    Only needed for boto3 api calls
    :param t: list: the list of aws tags
    :return: dict: python dict of the tags

    >>> from pprint import pprint
    >>> pprint(aws_tags_to_dict([{'Key': 'a', 'Value': 'b'}, {'Key': 'c', 'Value': 'd'}]))
    {'a': 'b', 'c': 'd'}
    """
    return {v['Key']: v['Value'] for v in t}


def get_autoscaling_group_and_processes_to_suspend(as_conn, app, log_file):
    if 'autoscale' in app.keys() and 'name' in app['autoscale'].keys() and app['autoscale']['name']:
        as_name = app['autoscale']['name']
        as_list = as_conn.describe_auto_scaling_groups(
            AutoScalingGroupNames=[as_name]
        )['AutoScalingGroups']

        if len(as_list) == 1:
            as_group = as_list[0]
            log("INFO: Auto-scaling group {0} found".format(as_name), log_file)

            # Determine if the auto-scaling Launch and/or Terminate processes should be suspended
            # (i.e. they are already suspended and should remain as is)
            as_processes_to_suspend = {'Launch': None, 'Terminate': None}
            for suspended_process in as_group['SuspendedProcesses']:
                if suspended_process['ProcessName'] in ['Launch', 'Terminate']:
                    del as_processes_to_suspend[suspended_process['ProcessName']]
                    log("INFO: Auto-scaling group {0} {1} process is already suspended"
                        .format(as_name, suspended_process['ProcessName']), log_file)

            return as_group['AutoScalingGroupName'], as_processes_to_suspend.keys()
        else:
            log("WARNING: Auto-scaling group {0} not found".format(as_name), log_file)
            if len(as_list) > 1:
                for ec2_as in as_list:
                    log("WARNING:    Auto-scaling group found: {0}".format(ec2_as['AutoScalingGroupName']), log_file)
            else:
                log("WARNING: No auto-scaling group found", log_file)
    return None, None


def suspend_autoscaling_group_processes(as_conn, as_group, as_group_processes_to_suspend, log_file):
    if as_group and as_group_processes_to_suspend:
        log("Suspending auto-scaling group processes {0}".format(as_group_processes_to_suspend), log_file)
        as_conn.suspend_processes(
            AutoScalingGroupName=as_group,
            ScalingProcesses=as_group_processes_to_suspend
        )


def resume_autoscaling_group_processes(as_conn, as_group, as_group_processes_to_resume, log_file):
    if as_group and as_group_processes_to_resume:
        log("Resuming auto-scaling group processes {0}".format(as_group_processes_to_resume), log_file)
        as_conn.resume_processes(
            AutoScalingGroupName=as_group,
            ScalingProcesses=as_group_processes_to_resume
        )


def create_userdata_launchconfig_update_asg(ami_id, cloud_connection, app, config, log_file, update_as_params=False):
    if check_autoscale_exists(cloud_connection, app['autoscale']['name'], app['region']):
        userdata = generate_userdata(config['bucket_s3'], config.get('bucket_region', app['region']),
                                     config['ghost_root_path'])
        if userdata:
            launch_config = create_launch_config(cloud_connection, app, userdata, ami_id)
            log("Launch configuration [{0}] created.".format(launch_config.name), log_file)
            if launch_config:
                update_auto_scale(cloud_connection, app, launch_config, log_file, update_as_params)
                if purge_launch_configuration(cloud_connection, app, config.get('launch_configuration_retention', 5)):
                    log("Old launch configurations removed for this app", log_file)
                else:
                    log("ERROR: Purge launch configurations failed", log_file)
                return True
            else:
                log("ERROR: Cannot update autoscaling group", log_file)
                return False
        else:
            log("ERROR: Cannot generate userdata. The bootstrap.sh file can maybe not be found.", log_file)
            return False
    else:
        log("ERROR: Autoscaling group [{0}] does not exist".format(app['autoscale']['name']), log_file)
        return False


def _format_launchconfig_name(app, app_color, only_prefix=False):
    return "launchconfig.{}.{}.{}.{}{}.{}".format(
            app['env'], app['region'], app['role'], app['name'],
            '.{}'.format(app_color) if app_color else '',
            time.strftime('%Y%m%d-%H%M%S', time.localtime()) if not only_prefix else "")


def create_launch_config(cloud_connection, app, userdata, ami_id):
    blue_green, app_color = get_blue_green_from_app(app)

    launchconfig_name = _format_launchconfig_name(app, app_color)
    conn_as = cloud_connection.get_connection(app['region'], ["ec2", "autoscale"])
    if 'root_block_device' in app['environment_infos']:
        bdm = create_block_device(cloud_connection, app['region'], app['environment_infos']['root_block_device'])
    else:
        bdm = create_block_device(cloud_connection, app['region'])
    instance_monitoring = app.get('instance_monitoring', False)
    launch_config = cloud_connection.launch_service(
        ["ec2", "autoscale", "LaunchConfiguration"],
        connection=conn_as,
        name=launchconfig_name,
        image_id=ami_id, key_name=app['environment_infos']['key_name'],
        security_groups=app['environment_infos']['security_groups'],
        user_data=userdata, instance_type=app['instance_type'], kernel_id=None,
        ramdisk_id=None, block_device_mappings=[bdm],
        instance_monitoring=instance_monitoring, spot_price=None,
        instance_profile_name=app['environment_infos']['instance_profile'], ebs_optimized=False,
        associate_public_ip_address=app['environment_infos'].get('public_ip_address', True),
        volume_type=None,
        delete_on_termination=True, iops=None,
        classic_link_vpc_id=None, classic_link_vpc_security_groups=None)
    conn_as.create_launch_configuration(launch_config)
    return launch_config


def check_autoscale_exists(cloud_connection, as_name, region):
    conn_as = cloud_connection.get_connection(region, ['autoscaling'], boto_version='boto3')
    return get_autoscaling_group_object(conn_as, as_name) is not None


def purge_launch_configuration(cloud_connection, app, retention):
    """
    Removes the old launch configurations except the `retention`th latest
    :param cloud_connection: object:
    :param app: object:
    :param retention: int:
    :return: bool:
    """
    conn_as = cloud_connection.get_connection(app['region'], ["autoscaling"], boto_version='boto3')
    paginator = conn_as.get_paginator('describe_launch_configurations')
    lcs = []
    for page in paginator.paginate():
        lcs = lcs + page['LaunchConfigurations']

    blue_green, app_color = get_blue_green_from_app(app)
    launchconfig_prefix = _format_launchconfig_name(app, app_color, only_prefix=True)

    lcs = [lc for lc in lcs if lc['LaunchConfigurationName'].startswith(launchconfig_prefix)]
    lcs = sorted(lcs, key=lambda lc: lc['CreatedTime'], reverse=True)[retention:]

    for lc in lcs:
        try:
            conn_as.delete_launch_configuration(LaunchConfigurationName=lc['LaunchConfigurationName'])
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') != 'ResourceInUse':
                raise
    return True


def update_auto_scale(cloud_connection, app, launch_config, log_file, update_as_params=False):
    """ Update the AutoScaling parameters.

        :param  cloud_connection
        :param  app               dict  The app config define in Ghost.
        :param  launch_config     boto obj  The new launch configuration.
        :param  log_file          log file obj
        :param  update_as_params  Bool  If set to True the desired_capacity/min_size/max_size/subnets will be updated
        :return   None
    """
    as_conn = cloud_connection.get_connection(app['region'], ['autoscaling'], boto_version='boto3')
    connvpc = cloud_connection.get_connection(app['region'], ["vpc"])
    az = [i.availability_zone for i in connvpc.get_all_subnets(subnet_ids=app['environment_infos']['subnet_ids'])]
    as_group = get_autoscaling_group_object(as_conn, app['autoscale']['name'])
    if launch_config:
        as_conn.update_auto_scaling_group(
            AutoScalingGroupName=app['autoscale']['name'],
            LaunchConfigurationName=launch_config.name
        )
    if update_as_params:
        as_conn.update_auto_scaling_group(
            AutoScalingGroupName=app['autoscale']['name'],
            MinSize=app['autoscale']['min'],
            MaxSize=app['autoscale']['max'],
            AvailabilityZones=az,
            VPCZoneIdentifier=','.join(app['environment_infos']['subnet_ids'])
        )
    asg_metrics = ["GroupMinSize", "GroupMaxSize", "GroupDesiredCapacity", "GroupInServiceInstances",
                   "GroupPendingInstances", "GroupStandbyInstances", "GroupTerminatingInstances", "GroupTotalInstances"]
    if boolify(app['autoscale'].get('enable_metrics', True)):
        log("Enabling Autoscaling group [{0}] metrics ({1}).".format(app['autoscale']['name'], asg_metrics), log_file)
        as_conn.enable_metrics_collection(
            AutoScalingGroupName=app['autoscale']['name'],
            Granularity='1Minute',
        )
    else:
        log("Disabling Autoscaling group [{0}] metrics ({1}).".format(app['autoscale']['name'], asg_metrics), log_file)
        as_conn.disable_metrics_collection(
            AutoScalingGroupName=app['autoscale']['name'],
        )
    log("Autoscaling group [{0}] updated.".format(app['autoscale']['name']), log_file)
    if update_as_params:
        app_tags = get_app_tags(app, log_file)
        as_tags = get_autoscale_tags(as_group, log_file)
        to_delete_tags = [v for k, v in as_tags.items() if k and k not in app_tags.keys() and v]
        if to_delete_tags and len(to_delete_tags):
            as_conn.delete_tags(Tags=to_delete_tags)
        as_conn.create_or_update_tags(Tags=app_tags.values())
        log("Autoscaling tags [{0}] updated.".format(app['autoscale']['name']), log_file)


def get_autoscale_tags(as_group, log_file):
    """ Return the current Tags set for an AutoScaling.

        :param as_group
        :param log_file
        :return  dict  Every tags defined for this AutoScaling
    """
    as_tags = {}
    for tag in as_group['Tags']:
        as_tags[tag['Key']] = tag
    log("Tags currently set  {0}".format(", ".join(as_tags.keys())), log_file)
    return as_tags


def get_app_tags(app, log_file=None):
    """ Return the tags defined for this application.

        :param  app dict The application object
        :param  log_file obj Log file objet
        :return dict Every tags defined for this Ghost Application

        >>> app_original = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'autoscale': {'name': 'asg-mod1'}, 'environment_infos': {'instance_tags':[]}}
        >>> len(get_app_tags(app_original)) == 4
        True

        >>> app_original = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'autoscale': {'name': 'asg-mod2'}, 'environment_infos': {'instance_tags':[{'tag_name': 'Name', 'tag_value': 'Prod.Server1'}]}}
        >>> len(get_app_tags(app_original)) == 5
        True

    """
    tags_app = {}
    for ghost_tag_key, ghost_tag_val in {'app': 'name', 'app_id': '_id', 'env': 'env', 'role': 'role'}.items():
        tags_app[ghost_tag_key] = {
            'Key': ghost_tag_key,
            'Value': str(app[ghost_tag_val]),
            'PropagateAtLaunch': True,
            'ResourceId': app['autoscale']['name'],
            'ResourceType': 'auto-scaling-group'
        }
    if app.get('blue_green') and app['blue_green'].get('color'):
        tags_app['color'] = {
            'Key': 'color',
            'Value': app['blue_green']['color'],
            'PropagateAtLaunch': True,
            'ResourceId': app['autoscale']['name'],
            'ResourceType': 'auto-scaling-group'
        }
    i_tags = app['environment_infos']['instance_tags'] if 'instance_tags' in app['environment_infos'] else []
    for app_tag in i_tags:
        tags_app[app_tag['tag_name']] = {
            'Key': app_tag['tag_name'],
            'Value': app_tag['tag_value'],
            'PropagateAtLaunch': True,
            'ResourceId': app['autoscale']['name'],
            'ResourceType': 'auto-scaling-group'
        }
    if log_file:
        log("[{0}] will be updated with: {1}".format(app['autoscale']['name'], ", ".join(tags_app.keys())), log_file)
    return tags_app


def normalize_application_tags(app_original, app_updated):
    """ Simple function to normalize application tags when application is created or updated.
        It aims to ensure that required tags are always well defined.

        :param  app_original  string: The ghost "app" object before modification.
        :param  app_updated   string: The ghost "app" object with the new modifications.
        :return list  A list of dict. Each dict define a tag

        Test with only the default tag Name

        >>> from copy import deepcopy
        >>> from pprint import pprint
        >>> app_original = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [{'name': 'mod1', 'git_repo': 'git@github.com/test/mod1'}, {'name': 'mod2', 'git_repo': 'git@github.com/test/mod2'}], 'environment_infos': {'instance_tags':[]}}
        >>> app_updated = deepcopy(app_original)
        >>> pprint(sorted(normalize_application_tags(app_original, app_updated), key=lambda d: d['tag_name']))
        [{'tag_name': 'Name', 'tag_value': 'ec2.prod.webfront.app1'}]

        Test with a custom Tag Name

        >>> app_original = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [{'name': 'mod1', 'git_repo': 'git@github.com/test/mod1'}, {'name': 'mod2', 'git_repo': 'git@github.com/test/mod2'}], 'environment_infos': {'instance_tags':[]}}
        >>> app_updated = deepcopy(app_original)
        >>> app_updated['environment_infos']['instance_tags'] = [{'tag_name': 'Name', 'tag_value': 'Prod.Server1'}]
        >>> pprint(sorted(normalize_application_tags(app_original, app_updated), key=lambda d: d['tag_name']))
        [{'tag_name': 'Name', 'tag_value': 'Prod.Server1'}]

        Test with a custom Tag Name build with variables

        >>> app_original = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [{'name': 'mod1', 'git_repo': 'git@github.com/test/mod1'}, {'name': 'mod2', 'git_repo': 'git@github.com/test/mod2'}], 'environment_infos': {'instance_tags':[{'tag_name': 'Name', 'tag_value': 'Prod.Server1'}]}}
        >>> pprint(sorted(normalize_application_tags(app_original, app_updated), key=lambda d: d['tag_name']))
        [{'tag_name': 'Name', 'tag_value': 'Prod.Server1'}]

        Test with a custom tag

        >>> app_original = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [{'name': 'mod1', 'git_repo': 'git@github.com/test/mod1'}, {'name': 'mod2', 'git_repo': 'git@github.com/test/mod2'}], 'environment_infos': {'instance_tags':[]}}
        >>> app_updated = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [{'name': 'mod1', 'git_repo': 'git@github.com/test/mod1'}, {'name': 'mod2', 'git_repo': 'git@github.com/test/mod2'}], 'environment_infos': {'instance_tags':[{'tag_name': 'billing', 'tag_value': 'account1'}]}}
        >>> pprint(sorted(normalize_application_tags(app_original, app_updated), key=lambda d: d['tag_name']))
        [{'tag_name': 'Name', 'tag_value': 'ec2.prod.webfront.app1'},
         {'tag_name': 'billing', 'tag_value': 'account1'}]

        Test with a custom tag updated

        >>> app_original = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [{'name': 'mod1', 'git_repo': 'git@github.com/test/mod1'}, {'name': 'mod2', 'git_repo': 'git@github.com/test/mod2'}], 'environment_infos': {'instance_tags':[{'tag_name': 'billing', 'tag_value': 'account1'}]}}
        >>> app_updated = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [{'name': 'mod1', 'git_repo': 'git@github.com/test/mod1'}, {'name': 'mod2', 'git_repo': 'git@github.com/test/mod2'}], 'environment_infos': {'instance_tags':[{'tag_name': 'billing', 'tag_value': 'account2'}]}}
        >>> pprint(sorted(normalize_application_tags(app_original, app_updated), key=lambda d: d['tag_name']))
        [{'tag_name': 'Name', 'tag_value': 'ec2.prod.webfront.app1'},
         {'tag_name': 'billing', 'tag_value': 'account2'}]

    """
    app_tags = []
    reserved_ghost_tags = ['app', 'app_id', 'env', 'role', 'color']
    default_tag_name_value = "ec2.{env}.{role}.{app}".format(env=app_original['env'], role=app_original['role'],
                                                             app=app_original['name'])

    custom_tags = (app_updated['environment_infos']['instance_tags']
                   if 'instance_tags' in app_updated['environment_infos'] else [])

    if 'Name' not in [i['tag_name'] for i in custom_tags]:
        app_tags.append({'tag_name': 'Name', 'tag_value': default_tag_name_value})

    for tag in custom_tags:
        if tag['tag_name'] not in reserved_ghost_tags:
            app_tags.append({'tag_name': tag['tag_name'], 'tag_value': tag['tag_value']})
    return app_tags


def push_file_to_s3(cloud_connection, bucket_name, region, bucket_key_path, file_path):
    """
    Takes a file (path) in argument and uploads it to a S3 bucket on the given path.
    """
    conn = cloud_connection.get_connection(region, ["s3"])
    bucket = conn.get_bucket(bucket_name)

    key = bucket.new_key(bucket_key_path)
    key.set_contents_from_filename(file_path)
    key.close()


def download_file_from_s3(cloud_connection, bucket_name, region, bucket_key_path, file_path):
    try:
        conn = cloud_connection.get_connection(region, ["s3"])
        bucket = conn.get_bucket(bucket_name)

        key = bucket.get_key(bucket_key_path)
        key.get_contents_to_filename(file_path)
        key.close(True)
    except:
        # An error occured, so the downloaded file might be corrupted, deleting it.
        if os.path.exists(file_path):
            os.remove(file_path)
