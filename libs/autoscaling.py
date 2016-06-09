#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Library to easily manage instances in an Autoscaling Group."""

from .ec2 import destroy_ec2_instances

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

def flush_instances_update_autoscale(as_conn, ec2_conn, app, log_file):
    """
    Updates the AutoScale group with min 0, max 0, desired 0
    Trigger a destroy all instances

    :param  as_conn  string: The boto2 Autoscaling Group connection.
    :param  ec2_conn string: The boto2 EC2 connection.
    :param  app: The Ghost application
    :param  log_file: Log file path
    """
    as_group = as_conn.get_all_groups(names=[app['autoscale']['name']])[0]
    setattr(as_group, 'desired_capacity', 0)
    setattr(as_group, 'min_size', 0)
    setattr(as_group, 'max_size', 0)
    as_group.update()
    destroy_ec2_instances(ec2_conn, app, log_file)
