# -*- coding: utf-8 -*-

"""
    The Rolling update library aims to create a sweet way to destroy EC2 instances and let the AutoScale renew them smoothly.
"""

import time
from fabric.colors import green as _green, yellow as _yellow, red as _red

from ghost_tools import GCallException, log, split_hosts_list
from ghost_aws import suspend_autoscaling_group_processes, resume_autoscaling_group_processes
from libs import load_balancing

from .autoscaling import get_autoscaling_group_object, update_auto_scaling_group_attributes
from .autoscaling import check_autoscale_instances_lifecycle_state
from .blue_green import get_blue_green_from_app
from .ec2 import find_ec2_running_instances, destroy_specific_ec2_instances


class RollingUpdate:
    """ Class which will manage the safe destroy process """

    def __init__(self, cloud_connection, app, safe_infos, log_file):
        """
            :param  app:          dict: Ghost object which describe the application parameters.
            :param  safe_infos:   dict: The safe deployment parameters.
            :param  log_file:     object for logging
        """
        self.cloud_connection = cloud_connection
        self.app = app
        self.safe_infos = safe_infos

        self.log_file = log_file

        as_name = app['autoscale']['name']
        self.as_name = as_name

        app_name = app['name']
        app_env = app['env']
        app_role = app['role']
        app_region = app['region']
        app_blue_green, app_color = get_blue_green_from_app(app)

        self.hosts_list = find_ec2_running_instances(cloud_connection, app_name, app_env, app_role, app_region, ghost_color=app_color)

    def elb_rolling_update(self, instances_list):
        """ Manage the safe destroy process for the ELB.

            :param  instances_list  list: Instances on which to destroy (list of dict. ex: [{'id':XXX, 'private_ip_address':XXXX}...]).
            :return                True if operation successed or raise an Exception.
        """
        if not self.as_name:
            raise GCallException('Cannot continue because there is no AutoScaling Group configured')

        app_region = self.app['region']

        as_conn = self.cloud_connection.get_connection(app_region, ['autoscaling'], boto_version='boto3')
        lb_mgr = load_balancing.get_lb_manager(self.cloud_connection, app_region, load_balancing.LB_TYPE_AWS_CLB)
        destroy_asg_policy = ['OldestLaunchConfiguration']

        try:
            elb_instances = lb_mgr.get_instances_status_from_autoscale(self.as_name, self.log_file)
            asg_infos = get_autoscaling_group_object(as_conn, self.as_name)
            if not len(elb_instances):
                raise GCallException('Cannot continue because there is no ELB configured in the AutoScaling Group')
            elif len([i for i in elb_instances.values() if 'outofservice' in i.values()]):
                raise GCallException('Cannot continue because one or more instances are in the out of service state')
            elif not check_autoscale_instances_lifecycle_state(asg_infos['Instances']):
                raise GCallException('Cannot continue because one or more instances are not in InService Lifecycle state')
            else:
                group_size = len(instances_list)
                original_termination_policies = asg_infos['TerminationPolicies']

                log(_green('Suspending "Terminate" process in the AutoScale and provisioning %s instance(s)'
                           % group_size), self.log_file)
                suspend_autoscaling_group_processes(as_conn, self.as_name, ['Terminate'], self.log_file)
                update_auto_scaling_group_attributes(as_conn, self.as_name, asg_infos['MinSize'],
                                                     asg_infos['MaxSize'] + group_size, asg_infos['DesiredCapacity'] + group_size)

                log(_green('Deregister old instances from the Load Balancer (%s)' %
                           str([host['id'] for host in instances_list])), self.log_file)
                lb_mgr.deregister_instances_from_lbs(self.as_name, [host['id'] for host in instances_list],
                                                     self.log_file)
                wait_con_draining = int(lb_mgr.get_lbs_max_connection_draining_value(self.as_name))
                log('Waiting {0}s: The connection draining time'.format(wait_con_draining), self.log_file)
                time.sleep(wait_con_draining)

                asg_updated_infos = get_autoscaling_group_object(as_conn, self.as_name)
                while len(asg_updated_infos['Instances']) < asg_updated_infos['DesiredCapacity']:
                    log('Waiting 30s because the instance(s) are not provisioned in the AutoScale', self.log_file)
                    time.sleep(30)
                    asg_updated_infos = get_autoscaling_group_object(as_conn, self.as_name)
                while not check_autoscale_instances_lifecycle_state(asg_updated_infos['Instances']):
                    log('Waiting 30s because the instance(s) are not in InService state in the AutoScale', self.log_file)
                    time.sleep(30)
                    asg_updated_infos = get_autoscaling_group_object(as_conn, self.as_name)

                while len([i for i in lb_mgr.get_instances_status_from_autoscale(self.as_name, self.log_file).values() if 'outofservice' in i.values()]):
                    log('Waiting 10s because the instance(s) are not in service in the ELB', self.log_file)
                    time.sleep(10)

                suspend_autoscaling_group_processes(as_conn, self.as_name, ['Launch', 'Terminate'], self.log_file)
                log(_green('Restore initial AutoScale attributes and destroy old instances for this group (%s)' % str([host['id'] for host in instances_list])), self.log_file)
                update_auto_scaling_group_attributes(as_conn, self.as_name, asg_infos['MinSize'], asg_infos['MaxSize'], asg_infos['DesiredCapacity'], destroy_asg_policy)
                destroy_specific_ec2_instances(self.cloud_connection, self.app, instances_list, self.log_file)

                resume_autoscaling_group_processes(as_conn, self.as_name, ['Terminate'], self.log_file)
                asg_updated_infos = get_autoscaling_group_object(as_conn, self.as_name)
                while len(asg_updated_infos['Instances']) > asg_updated_infos['DesiredCapacity']:
                    log('Waiting 20s because the old instance(s) are not removed from the AutoScale', self.log_file)
                    time.sleep(20)
                    asg_updated_infos = get_autoscaling_group_object(as_conn, self.as_name)

                update_auto_scaling_group_attributes(as_conn, self.as_name, asg_infos['MinSize'], asg_infos['MaxSize'], asg_infos['DesiredCapacity'], original_termination_policies)
                log(_green('%s instance(s) have been re-generated and are registered in their ELB' % group_size), self.log_file)
                return True
        except Exception as e:
            raise
        finally:
            resume_autoscaling_group_processes(as_conn, self.as_name, ['Launch', 'Terminate'], self.log_file)

    def do_rolling(self, rolling_strategy):
        """  Main entry point for Rolling Update process.

            :param  rolling_strategy string: The type of rolling strategy(1by1-1/3-25%-50%)
            :return True if operation succeed otherwise an Exception will be raised.
        """
        hosts = split_hosts_list(self.hosts_list, rolling_strategy) if rolling_strategy else [self.hosts_list]
        for host_group in hosts:
            if self.safe_infos['load_balancer_type'] == 'elb':
                self.elb_rolling_update(host_group)
#            elif self.safe_infos['load_balancer_type'] == 'alb':
            else:
                raise GCallException('Load balancer type not supported for Rolling update option')
            log('Waiting 10s before going on next instance group', self.log_file)
            time.sleep(10)
        return True
