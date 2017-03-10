"""
    Library to retrieve EC2 instance informations depending
    of their state.

"""
# -*- coding: utf-8 -*-
#!/usr/bin/env python

from ghost_log import log
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
    conn_as = cloud_connection.get_connection(region, ['autoscaling'], boto_version='boto3')
    conn = cloud_connection.get_connection(region, ["ec2"])
    # Retrieve running instances
    if ghost_color:
        running_instance_filters = {"tag:env": ghost_env, "tag:role": ghost_role, "tag:app": ghost_app, "tag:color": ghost_color, "instance-state-name": "running"}
    else:
        running_instance_filters = {"tag:env": ghost_env, "tag:role": ghost_role, "tag:app": ghost_app, "instance-state-name": "running"}
    running_instances = conn.get_only_instances(filters=running_instance_filters)
    hosts = []
    for instance in running_instances:
        # Instances in autoscale "Terminating:*" states are still "running" but no longer in the Load Balancer
        autoscale_instances = conn_as.describe_auto_scaling_instances(InstanceIds=[instance.id])['AutoScalingInstances']
        if not autoscale_instances or not autoscale_instances[0]['LifecycleState'] in ['Terminating', 'Terminating:Wait', 'Terminating:Proceed']:
            hosts.append({'id': instance.id, 'private_ip_address': instance.private_ip_address})
    return hosts

def destroy_ec2_instances(cloud_connection, app, log_file):
    """ Destroy all EC2 instances which matches the `ghost app` tags

        :param  cloud_connection: The app Cloud Connection object
        :param  app  string: The ghost "app" object.
        :param  log_file: Logging path
    """
    conn = cloud_connection.get_connection(app['region'], ["ec2"])
    app_blue_green, app_color = get_blue_green_from_app(app)
    running_instances = find_ec2_running_instances(cloud_connection, app['name'], app['env'], app['role'], app['region'], app_color)
    #Terminating instances
    instances = []
    for r in running_instances:
        instances.append(r['id'])
    if len(instances) > 0:
        log(instances, log_file)
        conn.terminate_instances(instance_ids=instances)
    else:
        log('No instances to destroy found', log_file)

def get_ec2_instance_status(cloud_connection, aws_region, instance_id):
    """ Get EC2 instance status

        :param  cloud_connection: The app Cloud Connection object
        :param  aws_region  string: The region to use
        :param  instance_id string: Instance ID to check
    """
    conn = cloud_connection.get_connection(region, ["ec2"], boto_version='boto3')
    ec2_status = conn.describe_instance_status(
        InstanceIds=[instance_id],
        MaxResults=1,
    )['InstanceStatuses'][0]
    return ec2_status
