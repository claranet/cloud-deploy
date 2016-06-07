#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Library to easily manage instances in an Autoscaling Group."""


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
