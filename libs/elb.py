"""

    Library to easily manage instances in an Elastic Load Balancer.
    Supported features:
        * Retrieve instances with their status in an ELB pool.
        * Add or remove instances in an ELB pool.
        * Check the instance status in the ELB pool.
        * Retrieve the connection draining value for an ELB.

@author: Matthieu BORET
"""
# -*- coding: utf-8 -*-
#!/usr/bin/env python

from ghost_log import log

def get_elb_from_autoscale(as_name, as_conn):
    """ Return a list of ELB names defined in
        the Autoscaling Group in parameter.

        :param  as_name  string: The Autoscaling Group name.
        :param  region   string: The boto Autoscaling Group connection.
        :return  a list of ELB names.
    """
    return as_conn.get_all_groups(names=[as_name])[0].load_balancers

def get_elb_instance_status_autoscaling_group(elb_conn, as_group, region, conn_as):
    """ Return a dict of instance ids as key and their status as value per elb.

        :param  elb_conn:  boto connection object to the ELB service.
        :param  as_group: string of the autoscaling group name.
        :param  region   string: The AWS Region of the Autoscaling Group.
        :return dict(ex: {'elb_XXX1':{'instance_id':'inservice/outofservice'}})
    """
    as_instance_status = {}
    for elb in get_elb_from_autoscale(as_group, conn_as):
        as_instance_status = {elb: {}}
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
        return True
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
