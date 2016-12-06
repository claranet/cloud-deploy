# -*- coding: utf-8 -*-
#!/usr/bin/env python

"""

    Library to easily manage instances in an Application Load Balancer.
    Supported features:
        * Retrieve instances with their status in an ALB pool.
        * Add or remove instances in an ALB pool.
        * Check the instance status in the ALB pool.
        * Retrieve the connection draining value for an ALB.

"""

from ghost_log import log
from .autoscaling import get_autoscaling_group_object

def alb_configure_health_check(alb_conn3, target_group_arn, protocol, port, path, interval, timeout, unhealthy_threshold, healthy_threshold):
    """
        Configures the ALB HealthCheck value
    """
    response = alb_conn3.modify_target_group(
        TargetGroupArn=target_group_arn,
        HealthCheckProtocol=protocol,
        HealthCheckPort=port,
        HealthCheckPath=path,
        HealthCheckIntervalSeconds=interval,
        HealthCheckTimeoutSeconds=timeout,
        HealthyThresholdCount=healthy_threshold,
        UnhealthyThresholdCount=unhealthy_threshold
    )
    return response

def get_alb_by_name(alb_conn3, alb_name):
    """
        :return the found ALB object
    """
    alb = alb_conn3.describe_load_balancers(
        Names=[alb_name],
        PageSize=1
    )['LoadBalancers'][0]
    return alb

def get_target_groups_from_autoscale(as_name, as_conn):
    """ Return a list of ALB target groups ARN defined in
        the Autoscaling Group in parameter.

        :param  as_name  string: The Autoscaling Group name.
        :param  as_conn  string: The boto Autoscaling Group connection.
        :return  a list of ALB target groups ARN.
    """
    if not as_name: # prevent to get all ASG and use first one...
        return []
    asg = get_autoscaling_group_object(as_conn, as_name)
    return asg['TargetGroupARNs'] if asg else []

def get_alb_target_status_autoscaling_group(alb_conn, as_group, conn_as):
    """ Return a dict of instance ids as key and their status as value per alb target group.

        :param  alb_conn: boto connection object to the ALB service.
        :param  as_group: string of the autoscaling group name.
        :param   conn_as: The boto Autoscaling Group connection.
        :return dict(ex: {'alb_XXX1':{'instance_id':'healthy/unhealthy'}})
    """
    as_instance_status = {}
    for tg_arn in get_target_groups_from_autoscale(as_group, conn_as):
        as_instance_status[tg_arn] = {}
        for target_health in alb_conn.describe_target_health(TargetGroupArn=tg_arn)['TargetHealthDescriptions']:
            target_id = target_health['Target']['Id']
            target_state = target_health['TargetHealth']['State']
            as_instance_status[tg_arn][target_id] = "healthy" if target_state.lower() == "healthy" else "unhealthy"
    return as_instance_status

def deregister_instance_from_alb(alb_conn, alb_tgs, hosts_id_list, log_file):
    """ Deregistrer one or multiple instances in the ALB pool.

        :param  alb_conn:  boto connection object to the ALB service.
        :param  alb_tgs:   list Target Group ARN of the Application Load Balancers.
        :param  hosts_id_list: list of instances ID to remove from the ELB pool.
        :param  log_file:  string  The log file
        :return boolean(True if succeed otherwise False)
    """
    try:
        for alb_tg_arn in alb_tgs:
            if len(alb_conn.deregister_targets(TargetGroupArn=alb_tg_arn, Targets=hosts_id_list)) != len(hosts_id_list):
                log("Failed to deregister instances {0} in the ALB {1}" .format(str(hosts_id_list), alb_tg_arn), log_file)
                raise
            else:
                log("Instances {0} well deregistered in the ALB {1}" .format(str(hosts_id_list), alb_tg_arn), log_file)
        return True
    except Exception as e:
        log("Exception during deregister operation: {0}" .format(str(e)),log_file)
        raise

def register_instance_from_alb(alb_conn, alb_tgs, hosts_id_list, log_file):
    """ Deregistrer one or multiple instances in the ALB pool.

        :param  alb_conn:  boto connection object to the ALB service.
        :param  alb_tgs:   list Target Group ARN of the Application Load Balancers.
        :param  hosts_id_list: list of instances ID to remove from the ELB pool.
        :param  log_file:  string  The log file
        :return boolean(True if succeed otherwise False)
    """
    try:
        for alb_tg_arn in alb_tgs:
            if len(alb_conn.register_targets(TargetGroupArn=alb_tg_arn, Targets=hosts_id_list)) != len(hosts_id_list):
                log("Failed to register instances {0} in the ALB {1}" .format(str(hosts_id_list), alb_tg_arn), log_file)
                raise
            else:
                log("Instances {0} well registered in the ALB {1}" .format(str(hosts_id_list), alb_tg_arn), log_file)
        return True
    except Exception as e:
        log("Exception during deregister operation: {0}" .format(str(e)),log_file)
        raise

def get_alb_deregistration_delay_value(alb_conn, alb_tgs):
    """ Return the biggest connection draining value for the list of alb in parameters.

        :param  alb_conn:  boto connection object to the ALB service.
        :param  alb_tgs:   list Target Group ARN of the Application Load Balancers.
        :return  int  The value in seconds of the connection draining.
    """
    values = []
    for alb_tg in alb_tgs:
        attrs = alb_conn.describe_target_group_attributes(TargetGroupArn=alb_tg)['Attributes']
        for at in attrs:
            if at['Key'] == 'deregistration_delay.timeout_seconds':
                values.append(int(at['Value']))
    return max(values)
