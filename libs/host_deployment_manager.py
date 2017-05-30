# -*- coding: utf-8 -*-

"""

    The Safe Deployment library aims to create a sweet way to deploy on EC2 instances.
    The process is:
        * Check that every instances in the Load Balancer(Haproxy or ELB or ALB) are in service and are enough to perform the safe deployment.
        * Split the instances list according the deployment type choosen(1by1-1/3-25%-50%).
        * Before begin to deploy on the instances group, remove them from their Load Balancer(Haproxy or ELB)
        * Wait a moment(depends on the connection draining value for the ELB and/or the custom value defines in Ghost)
        * Launch the standard deployment process
        * Wait a moment(depends on the custom value defines in Ghost)
        * Add the updated instances in their Load Balancer.
        * Wait until instances become healthly.
        * Do the same process for the next instance groups.
    This library works with one or more Load Balancers per Autoscaling Group.

    For AutoScaling Group with one or more Haproxy as Load Balancer, the safe deployment process works with Hapi only:
    https://bitbucket.org/morea/ghost.hapi.s4m/src

"""

import time
import haproxy

from ghost_tools import GCallException
from ghost_tools import log, split_hosts_list

from .deploy import launch_deploy, launch_executescript
from .ec2 import find_ec2_running_instances
from .elb import get_elb_instance_status_autoscaling_group, get_connection_draining_value, register_instance_from_elb, deregister_instance_from_elb
from .alb import get_alb_target_status_autoscaling_group, get_alb_deregistration_delay_value, register_instance_from_alb, deregister_instance_from_alb

class SafeDeployment():
    """ Class which will manage the safe deployment process """

    def __init__(self, cloud_connection, app, module, hosts_list, log_file, safe_infos, fabric_exec_strategy, as_name, safe_type=None, execute_script_params=None):
        """
            :param  module        dict: Ghost object wich describe the module parameters.
            :param  app           dict: Ghost object which describe the application parameters.
            :param  hosts_list:   list: Dictionnaries instances infos(id and private IP).
            :param  log_file:     object for logging
            :param  safe_infos:   dict: The safe deployment parameters.
            :param  lb_infos:     list: ELB names, ALB names or Haproxy IPs.
            :param  fabric_exec_strategy  string: Deployment strategy(serial or parrallel).
            :param  as_name:      string: The name of the Autoscaling Group.
            :param  safe_type:    string: Deploy or Executescript
            :param execute_script_params dict: All necessary params for `launch_executescript`
        """
        self.cloud_connection = cloud_connection
        self.app = app
        self.module = module
        self.hosts_list = hosts_list
        self.log_file = log_file
        self.fab_exec_strategy = fabric_exec_strategy
        self.safe_infos = safe_infos
        self.as_name = as_name
        self._safe_type = safe_type
        self._execute_script_params = execute_script_params

    def elb_safe_deployment(self, instances_list):
        """ Manage the safe deployment process for the ELB.

            :param  instances_list  list: Instances on which to deploy (list of dict. ex: [{'id':XXX, 'private_ip_address':XXXX}...]).
            :return                True if operation successed or raise an Exception.
        """
        if not self.as_name:
            raise GCallException('Cannot continue because there is no AutoScaling Group configured')

        app_region = self.app['region']

        as_conn = self.cloud_connection.get_connection(app_region, ['autoscaling'], boto_version='boto3')
        elb_conn = self.cloud_connection.get_connection(app_region, ["ec2", "elb"])

        elb_instances = get_elb_instance_status_autoscaling_group(elb_conn, self.as_name, as_conn)
        if not len(elb_instances):
            raise GCallException('Cannot continue because there is no ELB configured in the AutoScaling Group')
        elif len([i for i in elb_instances.values() if 'outofservice' in i.values()]):
            raise GCallException('Cannot continue because one or more instances are in the out of service state')
        else:
            deregister_instance_from_elb(elb_conn, elb_instances.keys(), [host['id'] for host in instances_list], self.log_file)
            wait_before_deploy = int(get_connection_draining_value(elb_conn, elb_instances.keys())) + int(self.safe_infos['wait_before_deploy'])
            log('Waiting {0}s: The connection draining time plus the custom value set for wait_before_deploy' .format(wait_before_deploy), self.log_file)
            time.sleep(wait_before_deploy)
            host_list = [host['private_ip_address'] for host in instances_list]
            if self._safe_type == 'executescript':
                launch_executescript(self.app,
                                     self._execute_script_params['script'], self._execute_script_params['context_path'], self._execute_script_params['sudoer_uid'], self._execute_script_params['jobid'],
                                     host_list, self.fab_exec_strategy, self.log_file, self._execute_script_params['env_vars'])
            else:
                launch_deploy(self.app, self.module, host_list, self.fab_exec_strategy, self.log_file)
            log('Waiting {0}s: The value set for wait_after_deploy' .format(self.safe_infos['wait_after_deploy']), self.log_file)
            time.sleep(int(self.safe_infos['wait_after_deploy']))
            register_instance_from_elb(elb_conn, elb_instances.keys(), [host['id'] for host in instances_list], self.log_file)
            while len([i for i in get_elb_instance_status_autoscaling_group(elb_conn, self.as_name, as_conn).values() if 'outofservice' in i.values()]):
                log('Waiting 10s because the instance is not in service in the ELB', self.log_file)
                time.sleep(10)
            log('Instances: {0} have been deployed and are registered in their ELB' .format(str([host['private_ip_address'] for host in instances_list])), self.log_file)
            return True

    def alb_safe_deployment(self, instances_list):
        """ Manage the safe deployment process for the Application Load Balancer.

            :param  instances_list  list: Instances on which to deploy(list of dict. ex: [{'id':XXX, 'private_ip_address':XXXX}...]).
            :return                True if operation successed or raise an Exception.
        """
        if not self.as_name:
            raise GCallException('Cannot continue because there is no AuoScaling Group configured')

        app_region = self.app['region']

        as_conn = self.cloud_connection.get_connection(app_region, ['autoscaling'], boto_version='boto3')
        alb_conn = self.cloud_connection.get_connection(app_region, ['elbv2'], boto_version='boto3')

        alb_targets = get_alb_target_status_autoscaling_group(alb_conn, self.as_name, as_conn)
        if not len(alb_targets):
            raise GCallException('Cannot continue because there is no ALB configured in the AutoScaling Group')
        elif len([i for i in alb_targets.values() if 'unhealthy' in i.values()]):
            raise GCallException('Cannot continue because one or more instances are in the unhealthy state')
        else:
            deregister_instance_from_alb(alb_conn, alb_targets.keys(), [{'Id': host['id']} for host in instances_list], self.log_file)
            wait_before_deploy = int(get_alb_deregistration_delay_value(alb_conn, alb_targets.keys())) + int(self.safe_infos['wait_before_deploy'])
            log('Waiting {0}s: The deregistation delay time plus the custom value set for wait_before_deploy' .format(wait_before_deploy), self.log_file)
            time.sleep(wait_before_deploy)
            host_list = [host['private_ip_address'] for host in instances_list]
            if self._safe_type == 'executescript':
                launch_executescript(self.app,
                                     self._execute_script_params['script'], self._execute_script_params['context_path'], self._execute_script_params['sudoer_uid'], self._execute_script_params['jobid'],
                                     host_list, self.fab_exec_strategy, self.log_file, self._execute_script_params['env_vars'])
            else:
                launch_deploy(self.app, self.module, host_list, self.fab_exec_strategy, self.log_file)
            log('Waiting {0}s: The value set for wait_after_deploy' .format(self.safe_infos['wait_after_deploy']), self.log_file)
            time.sleep(int(self.safe_infos['wait_after_deploy']))
            register_instance_from_alb(alb_conn, alb_targets.keys(), [{'Id': host['id']} for host in instances_list], self.log_file)
            while len([i for i in get_alb_target_status_autoscaling_group(alb_conn, self.as_name, as_conn).values() if 'unhealthy' in i.values()]):
                log('Waiting 10s because the instance is unhealthy in the ALB', self.log_file)
                time.sleep(10)
            log('Instances: {0} have been deployed and are registered in their ALB' .format(str([host['private_ip_address'] for host in instances_list])), self.log_file)
            return True

    def haproxy_configuration_validation(self, hapi, ha_urls, haproxy_backend):
        """ Check that every Haproxy have the same instances UP in their backend.

            :param   hapi     Class object of the Haproxy lib.
            :param   ha_urls  list  A list of Haproxy URL.
            :param   haproxy_backend  string: The name of the backend in Haproxy.
            :return           Boolean:  True if all configurations are equal, False otherwise.
        """
        ha_confs = []
        for ha_url in ha_urls:
            ha_confs.append(hapi.get_haproxy_conf(ha_url, True))
        return hapi.check_haproxy_conf(ha_confs, haproxy_backend)


    def haproxy_safe_deployment(self, instances_list):
        """ Manage the safe deployment process for the Haproxy.

            :param  instances_list  list: Instances on which to deploy(list of dict. ex: [{'id':XXX, 'private_ip_address':XXXX}...]).
            :return                 True if operation successed or raise an Exception.
        """
        lb_infos = [host['private_ip_address'] for host in find_ec2_running_instances(self.cloud_connection,
                     self.safe_infos['app_tag_value'], self.app['env'], 'loadbalancer', self.app['region'])]
        if lb_infos:
            hapi = haproxy.Haproxyapi(lb_infos, self.log_file, self.safe_infos['api_port'])
            ha_urls = hapi.get_haproxy_urls()
            if not self.haproxy_configuration_validation(hapi, ha_urls, self.safe_infos['ha_backend']):
                raise GCallException('Cannot initialize the safe deployment process because there are differences in the Haproxy \
                                    configuration files between the instances: {0}' .format(lb_infos))
            if not hapi.change_instance_state('disableserver', self.safe_infos['ha_backend'], [host['private_ip_address'] for host in instances_list]):
                raise GCallException('Cannot disable some instances: {0} in {1}. Deployment aborted' .format(instances_list, lb_infos))
            log('Waiting {0}s: The value set for wait_before_deploy' .format(self.safe_infos['wait_before_deploy']), self.log_file)
            time.sleep(int(self.safe_infos['wait_before_deploy']))
            host_list = [host['private_ip_address'] for host in instances_list]
            if self._safe_type == 'executescript':
                launch_executescript(self.app,
                                     self._execute_script_params['script'], self._execute_script_params['context_path'], self._execute_script_params['sudoer_uid'], self._execute_script_params['jobid'],
                                     host_list, self.fab_exec_strategy, self.log_file, self._execute_script_params['env_vars'])
            else:
                launch_deploy(self.app, self.module, host_list, self.fab_exec_strategy, self.log_file)
            log('Waiting {0}s: The value set for wait_after_deploy' .format(self.safe_infos['wait_after_deploy']), self.log_file)
            time.sleep(int(self.safe_infos['wait_after_deploy']))
            if not hapi.change_instance_state('enableserver', self.safe_infos['ha_backend'], [host['private_ip_address'] for host in instances_list]):
                raise GCallException('Cannot enabled some instances: {0} in {1}. Deployment aborded' .format(instances_list, lb_infos))
            # Add a sleep to let the time to pass the health check process
            time.sleep(5)
            if not self.haproxy_configuration_validation(hapi, ha_urls, self.safe_infos['ha_backend']):
                raise GCallException('Error in the post safe deployment process because there are differences in the Haproxy \
                                    configuration files between the instances: {0}. Instances: {1} have been deployed but not well enabled' .format(lb_infos, instances_list))
            if not hapi.check_all_instances_up(self.safe_infos['ha_backend'], hapi.get_haproxy_conf(ha_urls[0], True)):
                raise GCallException('Error in the post safe deployment process because some instances are disable or down in the Haproxy: {0}.' .format(lb_infos, instances_list))
            log('Instances: {0} have been deployed and are registered in their Haproxy' .format(str(instances_list)), self.log_file)
            return True
        else:
            raise GCallException('Cannot continue because no Haproxy found with the parameters: app_tag_value: {0}, app_env: {1}, app_role: loadbalancer,\
                                 app_region: {2}' .format(self.safe_infos['app_tag_value'], self.app['env'], self.app['region']))


    def safe_manager(self, safe_strategy):
        """  Global manager for the safe deployment process.

            :param  safe_strategy string: The type of safe deployment strategy(1by1-1/3-25%-50%)
            :return True if operation succeed otherwise an Exception will be raised.
        """
        for host_group in split_hosts_list(self.hosts_list, safe_strategy):
            if self.safe_infos['load_balancer_type'] == 'elb':
                self.elb_safe_deployment(host_group)
            elif self.safe_infos['load_balancer_type'] == 'alb':
                self.alb_safe_deployment(host_group)
            else:
                self.haproxy_safe_deployment(host_group)
        return True
