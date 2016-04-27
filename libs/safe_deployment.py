"""

    The Safe Deployment library aims to create a sweet way to deploy on EC2 instances.
    The process is:
        * Check that every instances in the Load Balancer(Haproxy or ELB) are in service and are enough to perform the safe deployment.
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
    https://bitbucket.org/mattboret/hapi

"""
import time
import haproxy
import boto.ec2.autoscale
import boto.ec2.elb

from ghost_tools import GCallException
from ghost_tools import log

from .deploy import launch_deploy
from .ec2 import find_ec2_running_instances
from .elb import get_elb_instance_status_autoscaling_group, get_connection_draining_value, register_instance_from_elb, deregister_instance_from_elb

class SafeDeployment():
    """ Class which will manage the safe deployment process """

    def __init__(self, app, module, hosts_list, log_file, safe_infos, fabric_exec_strategy, as_name, region):
        """
            :param  module        dict: Ghost object wich describe the module parameters.
            :param  app           dict: Ghost object which describe the application parameters.
            :param  hosts_list:   list: Dictionnaries instances infos(id and private IP).
            :param  log_file:     object for logging
            :param  safe_infos:   dict: The safe deployment parameters.
            :param  lb_infos:     list: ELB names or Haproxy IPs.
            :param  fabric_exec_strategy  string: Deployment strategy(serial or parrallel).
            :param  as_name:      string: The name of the Autoscaling Group.
            :param  region:       string: The AWS region.
        """
        self.app = app
        self.module = module
        self.hosts_list = hosts_list
        self.log_file = log_file
        self.fab_exec_strategy = fabric_exec_strategy
        self.safe_infos = safe_infos
        self.as_name = as_name
        self.region = region
        self.as_conn = boto.ec2.autoscale.connect_to_region(region)
        self.elb_conn = boto.ec2.elb.connect_to_region(region)

    def split_hosts_list(self, split_type):
        """ Return a list of multiple hosts list for the safe deployment.

            :param split_type:     string:  The way to split the hosts list(1by1-1/3-25%-50%).
            :return                list:    Multiple hosts list or raise an Exception is the safe
                                            deployment process cannot be perform.
        """
        if split_type == '1by1' and len(self.hosts_list) > 1:
            return [self.hosts_list[i:i + 1] for i in range(0, len(self.hosts_list), 1)]
        elif split_type == '1/3' and len(self.hosts_list) > 2:
            chunk = 3
        elif split_type == '25%' and len(self.hosts_list) > 3:
            chunk = 4
        elif split_type == '50%' and len(self.hosts_list) == 2 or len(self.hosts_list) > 3:
            chunk = 2
        else:
            log("Not enough instances to perform safe deployment. Number of instances: \
                {0} for safe deployment type: {1}" .format(str(len(self.hosts_list)), str(split_type)), self.log_file)
            raise GCallException("Cannot continue, not enought instances to perform the safe deployment")
        return [self.hosts_list[i::chunk] for i in range(chunk)]

    def elb_safe_deployment(self, instances_list):
        """ Manage the safe deployment process for the ELB.

            :param  instances_list  list: Instances on which to deploy(list of dict. ex: [{'id':XXX, 'private_ip_address':XXXX}...]).
            :return                True if operation successed or raise an Exception.
        """
        elb_instances = get_elb_instance_status_autoscaling_group(self.elb_conn, self.as_name, self.region, self.as_conn)
        if not len(elb_instances):
            raise GCallException('Cannot continue because there is no ELB configured in the AutoScaling Group')
        elif len([i for i in elb_instances.values() if 'outofservice' in i.values()]):
            raise GCallException('Cannot continue because one or more instances are in the out of service state')
        else:
            deregister_instance_from_elb(self.elb_conn, elb_instances.keys(), [host['id'] for host in instances_list], self.log_file)
            wait_before_deploy = int(get_connection_draining_value(self.elb_conn, elb_instances.keys())) + int(self.safe_infos['wait_before_deploy'])
            log('Waiting {0}s: The connection draining time more the custom value set for wait_before_deploy' .format(wait_before_deploy), self.log_file)
            time.sleep(wait_before_deploy)
            launch_deploy(self.app, self.module, [host['private_ip_address'] for host in instances_list], self.fab_exec_strategy, self.log_file)
            log('Waiting {0}s: The value set for wait_after_deploy' .format(self.safe_infos['wait_after_deploy']), self.log_file)
            time.sleep(int(self.safe_infos['wait_after_deploy']))
            register_instance_from_elb(self.elb_conn, elb_instances.keys(), [host['id'] for host in instances_list], self.log_file)
            while len([i for i in get_elb_instance_status_autoscaling_group(self.elb_conn, self.as_name, self.region, self.as_conn).values() if 'outofservice' in i.values()]):
                log('Waiting 10s because the instance is not in service in the ELB', self.log_file)
                time.sleep(10)
            log('Instances: {0} have been deployed and are registered in their ELB' .format(str([host['private_ip_address'] for host in instances_list])), self.log_file)
            return True

    def haproxy_configuration_validation(self, hapi, ha_urls):
        """ Check that every Haproxy have the same configuration.

            :param   hapi     Class object of the Haproxy lib.
            :param   ha_urls  list  A list of Haproxy URL.
            :return           Boolean:  True if all configurations are equal, False otherwise.
        """
        ha_confs = []
        for ha_url in ha_urls:
            ha_confs.append(hapi.get_haproxy_conf(ha_url, True))
        return hapi.check_haproxy_conf(ha_confs)


    def haproxy_safe_deployment(self, instances_list):
        """ Manage the safe deployment process for the Haproxy.

            :param  instances_list  list: Instances on which to deploy(list of dict. ex: [{'id':XXX, 'private_ip_address':XXXX}...]).
            :return                 True if operation successed or raise an Exception.
        """
        lb_infos = [host['private_ip_address'] for host in find_ec2_running_instances(self.safe_infos['app_tag_value'], self.app['env'], 'loadbalancer', self.app['region'])]
        if lb_infos:
            hapi = haproxy.Haproxyapi(lb_infos, self.log_file, self.safe_infos['api_port'])
            ha_urls = hapi.get_haproxy_urls()
            if not self.haproxy_configuration_validation(hapi, ha_urls):
                raise GCallException('Cannot initialize the safe deployment process because there is differences in the Haproxy \
                                    configuration files between the instances: {0}' .format(lb_infos))
            if not hapi.change_instance_state('disableserver', self.safe_infos['ha_backend'], [host['private_ip_address'] for host in instances_list]):
                raise GCallException('Cannot disabled some instances: {0} in {1}. Deployment aborded' .format(instances_list, lb_infos))
            log('Waiting {0}s: The value set for wait_before_deploy' .format(self.safe_infos['wait_before_deploy']), self.log_file)
            time.sleep(int(self.safe_infos['wait_before_deploy']))
            launch_deploy(self.app, self.module, [host['private_ip_address'] for host in instances_list], self.fab_exec_strategy, self.log_file)
            log('Waiting {0}s: The value set for wait_after_deploy' .format(self.safe_infos['wait_after_deploy']), self.log_file)
            time.sleep(int(self.safe_infos['wait_after_deploy']))
            if not hapi.change_instance_state('enableserver', self.safe_infos['ha_backend'], [host['private_ip_address'] for host in instances_list]):
                raise GCallException('Cannot enabled some instances: {0} in {1}. Deployment aborded' .format(instances_list, lb_infos))
            # Add a sleep to let the time to pass the health check process
            time.sleep(5)
            if not self.haproxy_configuration_validation(hapi, ha_urls):
                raise GCallException('Error in the post safe deployment process because there is differences in the Haproxy \
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
        for host_group in self.split_hosts_list(safe_strategy):
            if self.safe_infos['load_balancer_type'] == 'elb':
                self.elb_safe_deployment(host_group)
            else:
                self.haproxy_safe_deployment(host_group)
        return True
