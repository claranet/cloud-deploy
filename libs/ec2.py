# -*- coding: utf-8 -*-
"""
    Library to retrieve and manage EC2 instances.
"""

import os
import time
from fabric.colors import green as _green, yellow as _yellow, red as _red
from jinja2 import Environment, FileSystemLoader

from ghost_log import log
from ghost_tools import GCallException

from .blue_green import get_blue_green_from_app


def find_ec2_pending_instances(cloud_connection, ghost_app, ghost_env, ghost_role, region, as_group, ghost_color=None):
    """ Return a list of dict info only for the instances in pending state.

        :param  ghost_app  string: The value for the instance tag "app".
        :param  ghost_env  string: The value for the instance tag "env".
        :param  ghost_role  string: The value for the instance tag "role".
        :param  ghost_color  string: The value for the instance tag "color".
        :param  region  string: The AWS region where the instances are located.
        :return list of dict(ex: [{'id': instance_idXXX, 'private_ip_address': XXX_XXX_XXX_XXX},{...}])
    """
    conn_as = cloud_connection.get_connection(region, ['autoscaling'], boto_version='boto3')
    conn = cloud_connection.get_connection(region, ["ec2"])
    # Retrieve pending instances
    if ghost_color:
        pending_instance_filters = {"tag:env": ghost_env, "tag:role": ghost_role, "tag:app": ghost_app, "tag:color": ghost_color, "instance-state-name": "pending"}
    else:
        pending_instance_filters = {"tag:env": ghost_env, "tag:role": ghost_role, "tag:app": ghost_app, "instance-state-name": "pending"}
    pending_instances = conn.get_only_instances(filters=pending_instance_filters)
    pending_instances_ids = [instance.id for instance in pending_instances]
    autoscale_instances = []
    if as_group:
        autoscale_instances = conn_as.describe_auto_scaling_groups(
            AutoScalingGroupNames=[as_group],
            MaxRecords=1
        )['AutoScalingGroups'][0]['Instances']
    for autoscale_instance in autoscale_instances:
        # Instances in autoscale "Pending" state may not have their tags set yet
        if not autoscale_instance['InstanceId'] in pending_instances_ids and autoscale_instance['LifecycleState'] in ['Pending', 'Pending:Wait', 'Pending:Proceed']:
            pending_instances.append(conn.get_only_instances(instance_ids=[autoscale_instance['InstanceId']])[0])
    hosts = []
    for instance in pending_instances:
        hosts.append({'id': instance.id, 'private_ip_address': instance.private_ip_address})
    return hosts

def find_ec2_running_instances(cloud_connection, ghost_app, ghost_env, ghost_role, region, ghost_color=None):
    """ Return a list of dict info only for the running instances.

        :param  ghost_app  string: The value for the instance tag "app".
        :param  ghost_env  string: The value for the instance tag "env".
        :param  ghost_role  string: The value for the instance tag "role".
        :param  ghost_color  string: The value for the instance tag "color".
        :param  region  string: The AWS region where the instances are located.
        :return list of dict(ex: [{'id': instance_idXXX, 'private_ip_address': XXX_XXX_XXX_XXX},{...}])
    """
    return find_ec2_instances(cloud_connection, ghost_app, ghost_env, ghost_role, region, "running", ghost_color)

def find_ec2_instances(cloud_connection, ghost_app, ghost_env, ghost_role, region, ec2_state_filter=None, ghost_color=None):
    """ Return a list of dict info for the found instances.

        :param  ghost_app  string: The value for the instance tag "app".
        :param  ghost_env  string: The value for the instance tag "env".
        :param  ghost_role  string: The value for the instance tag "role".
        :param  ghost_color  string: The value for the instance tag "color".
        :param  region  string: The AWS region where the instances are located.
        :param  ec2_state_filter string: If we need to filter on an EC2 state
        :return list of dict(ex: [{'id': instance_idXXX, 'private_ip_address': XXX_XXX_XXX_XXX},{...}])
    """
    conn_as = cloud_connection.get_connection(region, ['autoscaling'], boto_version='boto3')
    conn = cloud_connection.get_connection(region, ["ec2"])
    # Retrieve instances
    instance_filters = {"tag:env": ghost_env, "tag:role": ghost_role, "tag:app": ghost_app}
    if ghost_color:
        instance_filters["tag:color"] = ghost_color
    if ec2_state_filter:
        instance_filters["instance-state-name"] = ec2_state_filter

    found_instances = conn.get_only_instances(filters=instance_filters)
    hosts = []
    for instance in found_instances:
        # Instances in autoscale "Terminating:*" states are still "running" but no longer in the Load Balancer
        autoscale_instances = conn_as.describe_auto_scaling_instances(InstanceIds=[instance.id])['AutoScalingInstances']
        if not autoscale_instances or not autoscale_instances[0]['LifecycleState'] in ['Terminating', 'Terminating:Wait', 'Terminating:Proceed']:
            hosts.append({'id': instance.id, 'private_ip_address': instance.private_ip_address, 'subnet_id': instance.subnet_id})
    return hosts

def get_ec2_instance(cloud_connection, region, instance_filters):
    """
    Find and return an EC2 object based on criteria given via `instance_filters` parameter.
    """
    conn = cloud_connection.get_connection(region, ["ec2"])
    found_instances = conn.get_only_instances(filters=instance_filters)
    return found_instances[0] if len(found_instances) else None

def destroy_ec2_instances(cloud_connection, app, log_file, ec2_state_filter=None):
    """ Destroy all EC2 instances which matches the `ghost app` tags

        :param  cloud_connection: The app Cloud Connection object
        :param  app  string: The ghost "app" object.
        :param  log_file: Logging path
        :param  ec2_state_filter string: If we need to filter on an EC2 state
        :return destroyed instance informations
    """
    app_blue_green, app_color = get_blue_green_from_app(app)
    found_instances = find_ec2_instances(cloud_connection, app['name'], app['env'], app['role'], app['region'], ec2_state_filter, app_color)
    return destroy_specific_ec2_instances(cloud_connection, app, found_instances, log_file)

def destroy_specific_ec2_instances(cloud_connection, app, found_instances, log_file):
    """ Destroy EC2 instances given in parameter

        :param  cloud_connection: The app Cloud Connection object
        :param  app  string: The ghost "app" object.
        :param  found_instances list: List of instances to terminate (ids)
        :param  log_file: Logging path
        :return destroyed instance informations
    """
    #Terminating instances
    instances = []
    for r in found_instances:
        instances.append(r['id'])
    conn = cloud_connection.get_connection(app['region'], ["ec2"])
    if len(instances) > 0:
        log(instances, log_file)
        conn.terminate_instances(instance_ids=instances)
        return found_instances
    else:
        log('No instances to destroy found', log_file)
        return []

def get_ec2_instance_status(cloud_connection, aws_region, instance_ids):
    """ Get EC2 instance status

        :param  cloud_connection: The app Cloud Connection object
        :param  aws_region  string: The region to use
        :param  instance_ids array[] string: Instances IDs to check
    """
    conn = cloud_connection.get_connection(aws_region, ["ec2"], boto_version='boto3')
    ec2_status = conn.describe_instance_status(
        InstanceIds=instance_ids,
    )['InstanceStatuses']
    return ec2_status

def test_ec2_instance_status(cloud_connection, aws_region, instance_ids, instance_state):
    """ Get EC2 instance status

        :param  cloud_connection: The app Cloud Connection object
        :param  aws_region  string: The region to use
        :param  instance_ids array[] string: Instances IDs to check
        :param  instance_state string: Instance to check
        :return True if every instances are in the instance_state provided.
    """
    conn = cloud_connection.get_connection(aws_region, ["ec2"], boto_version='boto3')
    ec2_statuses = conn.describe_instances(
        InstanceIds=instance_ids
    )["Reservations"][0]["Instances"]
    for instance in ec2_statuses:
        if not instance['State']['Name'] == instance_state:
            return False
    return True

def create_block_device(cloud_connection, region, app, rbd={}):
    """ Create all block device

        :param cloud_connection: The app Cloud Connection object
        :param aws_region  string: The region to use
        :param app string: The ghost "app" object
        :param rbd list: device mapping configuration
        :return the EC2 instance service object blockdevicemapping
    """
    conn = cloud_connection.get_connection(region, ["ec2"])
    dev_sda1 = cloud_connection.launch_service(
        ["ec2", "blockdevicemapping", "EBSBlockDeviceType"],
        connection=conn,
        delete_on_termination=True
    )
    # GP2 SSD by default
    if not rbd.get('type'):
        rbd['type'] = 'gp2'
    dev_sda1.volume_type = rbd['type']
    # 20GB Per default
    if not rbd.get('size'):
        rbd['size'] = 20
    dev_sda1.size = rbd['size']
    bdm = cloud_connection.launch_service(
        ["ec2", "blockdevicemapping", "BlockDeviceMapping"],
        connection=conn
    )
    if not rbd.get('name'):
        rbd['name'] = get_ami_root_block_device_mapping(conn, app['ami']) if app.get('ami') else "/dev/xvda"
    bdm[rbd['name']] = dev_sda1
    return bdm


def get_ami_root_block_device_mapping(conn, ami_id):
    """ Get ami root_block_device to mount

        :param cloud connection object
        :param ami-id string: the ami id of application 
        :return root block device path 
    """
    try:
        image = conn.get_all_images(image_ids=ami_id)
        path = image[0].block_device_mapping.keys()[0]
    except Exception as e:
        raise Exception("AMI root block device is not found: {}".format(str(e)))
    return path


def generate_userdata(bucket_s3, s3_region, ghost_root_path):
    """ Generates an EC2 userdata script using the Ghost's "stage1" script.

        :return The formatted stage1 script
    """
    jinja_templates_path = '%s/scripts' % ghost_root_path
    if os.path.exists('%s/stage1' % jinja_templates_path):
        loader = FileSystemLoader(jinja_templates_path)
        jinja_env = Environment(loader=loader)
        template = jinja_env.get_template('stage1')
        userdata = template.render(bucket_s3=bucket_s3, bucket_region=s3_region)
        return userdata
    else:
        return ""


def create_ec2_instance(cloud_connection, app, app_color, config, private_ip_address, subnet_id, log_file):
    """ Creates an EC2 instance and return its ID.

        :param  cloud_connection: The app Cloud Connection object
        :param  app: Ghost app document
        :param  app_color: Color value if BlueGreen application type
        :param  config: Ghost config settings
        :param  private_ip_address: Private IP address to use when creating the instance
        :param  subnet_id: Subnet to use when creating the instance
        :param  log_file: Logging file

        :return the EC2 instance object with all its details
    """
    log(_yellow(" INFO: Creating User-Data"), log_file)
    ghost_root_path = config.get('ghost_root_path', '/usr/local/share/ghost/')
    userdata = generate_userdata(config['bucket_s3'], config.get('bucket_region', app['region']), ghost_root_path)

    log(_yellow(" INFO: Creating EC2 instance"), log_file)
    if app['ami']:
        log(" CONF: AMI: {0}".format(app['ami']), log_file)
        log(" CONF: Region: {0}".format(app['region']), log_file)

        conn = cloud_connection.get_connection(app['region'], ["ec2"])
        interface = cloud_connection.launch_service(
                ["ec2", "networkinterface", "NetworkInterfaceSpecification"],
                subnet_id=subnet_id,
                groups=app['environment_infos']['security_groups'],
                associate_public_ip_address=app['environment_infos'].get('public_ip_address', True),
                private_ip_address=private_ip_address
                )
        interfaces = cloud_connection.launch_service(
                ["ec2", "networkinterface", "NetworkInterfaceCollection"],
                interface
                )
        if 'root_block_device' in app['environment_infos']:
            bdm = create_block_device(cloud_connection, app['region'], app, app['environment_infos']['root_block_device'])
        else:
            bdm = create_block_device(cloud_connection, app['region'], app, {})
        reservation = conn.run_instances(
            image_id=app['ami'],
            key_name=app['environment_infos']['key_name'],
            network_interfaces=interfaces,
            instance_type=app['instance_type'],
            instance_profile_name=app['environment_infos']['instance_profile'],
            user_data=userdata, block_device_map=bdm
        )

        # Getting instance metadata
        instance = reservation.instances[0]
        if instance.id:
            # Checking if instance is ready before tagging
            while not instance.state == u'running':
                log('Instance not running, waiting 10s before tagging.', log_file)
                time.sleep(10)
                instance.update()

            # Tagging
            for ghost_tag_key, ghost_tag_val in {'app': 'name', 'app_id': '_id', 'env': 'env', 'role': 'role'}.iteritems():
                log("Tagging instance [{id}] with '{tk}':'{tv}'".format(id=instance.id, tk=ghost_tag_key, tv=str(app[ghost_tag_val])), log_file)
                conn.create_tags([instance.id], {ghost_tag_key: str(app[ghost_tag_val])})
            if app_color:
                log("Tagging instance [{id}] with '{tk}':'{tv}'".format(id=instance.id, tk='color', tv=app_color), log_file)
                conn.create_tags([instance.id], {"color": app_color})

            tag_ec2_name = False
            if 'instance_tags' in app['environment_infos']:
                for app_tag in app['environment_infos']['instance_tags']:
                    log("Tagging instance [{id}] with '{tk}':'{tv}'".format(id=instance.id, tk=app_tag['tag_name'], tv=app_tag['tag_value']), log_file)
                    conn.create_tags([instance.id], {app_tag['tag_name']: app_tag['tag_value']})
                    if app_tag['tag_name'] == 'Name':
                        tag_ec2_name = True
            if not tag_ec2_name:
                ec2_name = "ec2.{0}.{1}.{2}".format(app['env'], app['role'], app['name'])
                log("Tagging instance [{id}] with '{tk}':'{tv}'".format(id=instance.id, tk='Name', tv=ec2_name), log_file)
                conn.create_tags([instance.id], {'Name': ec2_name})

            log(" CONF: Private IP: %s" % instance.private_ip_address, log_file)
            log(" CONF: Public IP: %s" % instance.ip_address, log_file)
            log(" CONF: Public DNS: %s" % instance.public_dns_name, log_file)
            return instance
        else:
            log(_red("ERROR: Cannot get instance metadata. Please check the AWS Console."), log_file)
            raise GCallException("ERROR: Cannot get instance metadata. Please check the AWS Console.")
    else:
        log(_red("ERROR: No AMI set, please use buildimage before"), log_file)
        raise GCallException("ERROR: No AMI set, please use buildimage before")

    return None
