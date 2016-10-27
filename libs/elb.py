"""

    Library to easily manage instances in an Elastic Load Balancer.
    Supported features:
        * Retrieve instances with their status in an ELB pool.
        * Add or remove instances in an ELB pool.
        * Check the instance status in the ELB pool.
        * Retrieve the connection draining value for an ELB.

"""
# -*- coding: utf-8 -*-
#!/usr/bin/env python

from ghost_log import log
from .autoscaling import get_autoscaling_group_object
from boto.ec2.elb.listelement import ListElement

def elb_configure_health_check(elb_conn3, elb_name, target, interval, timeout, unhealthy_threshold, healthy_threshold):
    """
        Configures the ELB HealthCheck value
    """
    response = elb_conn3.configure_health_check(
        LoadBalancerName=elb_name,
        HealthCheck={
            'Target': target,
            'Interval': interval,
            'Timeout': timeout,
            'UnhealthyThreshold': unhealthy_threshold,
            'HealthyThreshold': healthy_threshold
        }
    )
    return response

def get_elb_by_name(elb_conn3, elb_name):
    """
        :return the found ELB object
    """
    elb = elb_conn3.describe_load_balancers(
        LoadBalancerNames=[elb_name])['LoadBalancerDescriptions'][0]
    return elb

def copy_elb(elb_conn3, elb_name, source_elb_name, special_tag):
    """ Copy an existing ELB, currently copies basic configuration
        (Subnets, SGs, first listener), health check and tags.

        :param elb_conn3: boto3 elb client
        :param elb_name string: created ELB name
        :param source_elb_name string: source ELB name
        :return created ELB endpoint
    """
    source_elb = get_elb_by_name(elb_conn3, source_elb_name)
    source_elb_listener = source_elb['ListenerDescriptions'][0]['Listener']
    source_elb_tags = elb_conn3.describe_tags(
        LoadBalancerNames=[source_elb_name]
    )['TagDescriptions'][0]['Tags']
    source_elb_tags.append(special_tag)
    dest_elb_listener = {
        'Protocol': source_elb_listener['Protocol'],
        'LoadBalancerPort': source_elb_listener['LoadBalancerPort'],
        'InstanceProtocol': source_elb_listener['InstanceProtocol'],
        'InstancePort': source_elb_listener['InstancePort']
    }

    # Check if listener needs SSLCertificate
    if 'SSLCertificateId' in source_elb_listener:
        dest_elb_listener['SSLCertificateId'] = source_elb_listener['SSLCertificateId']

    # create ELB
    response = elb_conn3.create_load_balancer(
        LoadBalancerName=elb_name,
        Listeners=[dest_elb_listener],
        Subnets=source_elb['Subnets'],
        SecurityGroups=source_elb['SecurityGroups'],
        Scheme=source_elb['Scheme'],
        Tags=source_elb_tags
    )

    # Configure Healthcheck
    elb_conn3.configure_health_check(
        LoadBalancerName=elb_name,
        HealthCheck=source_elb['HealthCheck']
    )

    return response['DNSName']

def get_elb_from_autoscale(as_name, as_conn):
    """ Return a list of ELB names defined in
        the Autoscaling Group in parameter.

        :param  as_name  string: The Autoscaling Group name.
        :param  as_conn  string: The boto Autoscaling Group connection.
        :return  a list of ELB names.
    """
    if not as_name: # prevent to get all ASG and use first one...
        return []
    asg = get_autoscaling_group_object(as_conn, as_name)
    return asg['LoadBalancerNames'] if asg else []

def get_elb_dns_name(elb_conn, elb_name):
    """ Return the DNS name for the passed ELB

        :param  elb_conn:  boto connection object to the ELB service.
        :param  elb_name  string: The name of the Elastic Load Balancer.
        :return string
    """
    elb = elb_conn.get_all_load_balancers(load_balancer_names=[elb_name])[0]
    return elb.dns_name

def destroy_elb(elb_conn3, elb_name, log_file):
    """ Destroy the specified ELB

        :param  elb_conn3:  boto3 connection object to the ELB service.
        :param  elb_name  string: The name of the Elastic Load Balancer.
    """
    log("  INFO: Destroying ELB {0}".format(elb_name), log_file)
    response = elb_conn3.delete_load_balancer(LoadBalancerName=elb_name)

def register_elb_into_autoscale(as_name, as_conn3, elbs_to_deregister, elbs_to_register, log_file):
    """ Modify the AutoScale Group to set the list of ELB to use

    :param  as_name  string: string of the autoscaling group name.
    :param  as_conn3 string: The boto3 Autoscaling Group connection.
    :param  elbs_to_deregister  list: The name of the Elastic Load Balancers.
    :param  elbs_to_register  list: The name of the Elastic Load Balancers.
    :param  log_file string: The log file
    :return boolean(True if succeed otherwise False)
    """
    try:
        if elbs_to_deregister and len(elbs_to_deregister) > 0:
            as_conn3.detach_load_balancers(AutoScalingGroupName=as_name, LoadBalancerNames=elbs_to_deregister)
        if elbs_to_register and len(elbs_to_register) > 0:
            as_conn3.attach_load_balancers(AutoScalingGroupName=as_name, LoadBalancerNames=elbs_to_register)
    except Exception as e:
        log("Exception during register ELB operation into ASG: {0}" .format(str(e)), log_file)
        raise

def get_elb_instance_status_autoscaling_group(elb_conn, as_group, conn_as):
    """ Return a dict of instance ids as key and their status as value per elb.

        :param  elb_conn: boto connection object to the ELB service.
        :param  as_group: string of the autoscaling group name.
        :param   conn_as: The boto Autoscaling Group connection.
        :return dict(ex: {'elb_XXX1':{'instance_id':'inservice/outofservice'}})
    """
    as_instance_status = {}
    for elb in get_elb_from_autoscale(as_group, conn_as):
        as_instance_status[elb] = {}
        for instance in elb_conn.describe_instance_health(elb):
            as_instance_status[elb][instance.instance_id] = "inservice" if instance.state.lower() == "inservice" else "outofservice"
    return as_instance_status

def get_elb_instance_status(elb_conn, elb_names):
    """ Return a dict of instance ids as key and their status as value per elb.

        :param  elb_conn:  boto connection object to the ELB service.
        :param  elb_names  list: The name of the Elastic Load Balancers.
        :return dict(ex: {'elb_XXX1':{'instance_id':'inservice/outofservice'}})
    """
    as_instance_status = {}
    for elb in elb_names:
        as_instance_status[elb] = {}
        for instance in elb_conn.describe_instance_health(elb):
            as_instance_status[elb][instance.instance_id] = "inservice" if instance.state.lower() == "inservice" else "outofservice"
    return as_instance_status

def deregister_instance_from_elb(elb_conn, elb_names, hosts_id_list, log_file):
    """ Deregistrer one or multiple instances in the ELB pool.

        :param  elb_conn:  boto connection object to the ELB service.
        :param  elb_names: list The name of the Elastic Load Balancers.
        :param  hosts_id_list: list of instances ID to remove from the ELB pool.
        :param  log_file:  string  The log file
        :return boolean(True if succeed otherwise False)
    """
    try:
        for elb_name in elb_names:
            if not elb_conn.deregister_instances(elb_name, hosts_id_list).status:
                log("Failed to deregister instances {0} in the ELB {1}" .format(str(hosts_id_list), elb_name), log_file)
                raise
            else:
                log("Instances {0} well deregistered in the ELB {1}" .format(str(hosts_id_list), elb_name), log_file)
        return True
    except Exception as e:
        log("Exception during deregister operation: {0}" .format(str(e)),log_file)
        raise

def deregister_all_instances_from_elb(elb_conn, elbs_with_instances, log_file):
    """ Deregistrer one or multiple instances in the ELB pool.

        :param  elb_conn:  boto connection object to the ELB service.
        :param  elbs_with_instances: list The name of the Elastic Load Balancers, and all instances in one of them. (dict(ex: {'elb_XXX1':{'instance_id':'inservice/outofservice'}}))
        :param  log_file:  string  The log file
        :return boolean(True if succeed otherwise False)
    """
    try:
        for elb_name, elb_instances in elbs_with_instances.iteritems():
            if not elb_conn.deregister_instances(elb_name, elb_instances.keys()).status:
                log("Failed to deregister instances {0} in the ELB {1}" .format(str(elb_instances.keys()), elb_name), log_file)
                raise
            else:
                log("Instances {0} well deregistered in the ELB {1}" .format(str(elb_instances.keys()), elb_name), log_file)
        return True
    except Exception as e:
        log("Exception during deregister operation: {0}" .format(str(e)),log_file)
        raise

def register_instance_from_elb(elb_conn, elb_names, hosts_id_list, log_file):
    """ Registrer one or multiple instances in the ELB pool.

        :param  elb_conn:  boto connection object to the ELB service.
        :param  elb_names: list The name of the Elastic Load Balancers.
        :param  hosts_id_list: list of instances ID to add to the ELB pool.
        :param  log_file:  string  The log file
        :return boolean(True if succeed otherwise False)
    """
    try:
        for elb_name in elb_names:
            if not elb_conn.register_instances(elb_name, hosts_id_list).status:
                log("Failed to register instances {0} in the ELB {1}" .format(str(hosts_id_list), elb_name), log_file)
                raise
            else:
                log("Instances {0} well registered in the ELB {1}" .format(str(hosts_id_list), elb_name), log_file)
    except Exception as e:
        log("Exception during register operation: {0}" .format(str(e)), log_file)
        raise

def register_all_instances_to_elb(elb_conn, elb_names, instances, log_file):
    """ Registrer one or multiple instances in the ELB pool.

        :param  elb_conn:  boto connection object to the ELB service.
        :param  elb_names: list The name of the Elastic Load Balancers.
        :param  instances: list The name of the Elastic Load Balancers, and all instances in one of them. (dict(ex: {'elb_XXX1':{'instance_id':'inservice/outofservice'}}))
        :param  log_file:  string  The log file
        :return boolean(True if succeed otherwise False)
    """
    try:
        for elb_name in elb_names:
            for unused_elb_name, elb_instances in instances.iteritems():
                if not elb_conn.register_instances(elb_name, elb_instances.keys()).status:
                    log("Failed to register instances {0} in the ELB {1}" .format(str(elb_instances.keys()), elb_name), log_file)
                    raise
                else:
                    log("Instances {0} well registered in the ELB {1}" .format(str(elb_instances.keys()), elb_name), log_file)
    except Exception as e:
        log("Exception during register operation: {0}" .format(str(e)), log_file)
        raise

def get_connection_draining_value(elb_conn, elb_names):
    """ Return the biggest connection draining value for the list of elb in parameters.

        :param  elb_conn:  boto connection object to the ELB service.
        :param  elb_names: list The name of the Elastic Load Balancers.
        :return  int  The value in seconds of the connection draining.
    """
    return max([elb_conn.get_all_lb_attributes(elb).connection_draining.timeout for elb in elb_names])
