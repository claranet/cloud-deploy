#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Library to easily manage instances in an Autoscaling Group."""

from .ec2 import destroy_ec2_instances

def get_autoscaling_group_object(as_conn3, as_name):
    """
    Retrieves and return the AutoScale Group if exists

    :param  as_conn3 string: The boto3 Autoscaling Group connection.
    :param  as_name  string: The Autoscaling Group name.
    """
    asgs = as_conn3.describe_auto_scaling_groups(
        AutoScalingGroupNames=[as_name],
        MaxRecords=1
    )['AutoScalingGroups']

    return asgs[0] if len(asgs) else None

def get_instances_from_autoscaling(as_name, as_conn):
    """
    Return a list of instances associated with an AS Group.

    :param  as_name  string: The Autoscaling Group name.
    :param  as_conn  string: The boto3 Autoscaling Group connection.
    :return  a list of instances.
    """
    instances = []
    instances_paginator = as_conn.get_paginator('describe_auto_scaling_instances')
    instances_response_iterator = instances_paginator.paginate()

    for page in instances_response_iterator:
        for instance in page['AutoScalingInstances']:
            if instance['AutoScalingGroupName'] == as_name:
                instances.append(instance)

    return instances

def flush_instances_update_autoscale(as_conn, cloud_connection, app, log_file):
    """
    Updates the AutoScale group with min 0, max 0, desired 0
    Trigger a destroy all instances

    :param  as_conn  string: The boto3 Autoscaling Group connection.
    :param  cloud_connection: The app Cloud Connection object
    :param  app: The Ghost application
    :param  log_file: Log file path
    """
    update_auto_scaling_group_attributes(as_conn, app['autoscale']['name'], 0, 0, 0)
    destroy_ec2_instances(cloud_connection, app, log_file)

def update_auto_scaling_group_attributes(as_conn, as_name, as_min, as_max, as_desired):
    """
    Updates the AutoScale group attributes with given parameters

    :param  as_conn  string: The boto3 Autoscaling Group connection.
    """
    as_conn.update_auto_scaling_group(
        AutoScalingGroupName=as_name,
        MinSize=as_min,
        MaxSize=as_max,
        DesiredCapacity=as_desired,
    )

def check_autoscale_instances_lifecycle_state(instances, i_state='InService'):
    """
    Verify is every instances are in the right Lifecycle state `i_state`

    :param  instances array: list of instances to proceed, retrieved after a get_autoscaling_group_object() call
    :param i_state string: the Lifecycle state to check
    :return True if all instances are in the given lifecycle state
    """
    for instance in instances:
        if not instance['LifecycleState'] == i_state:
            return False
    return True
