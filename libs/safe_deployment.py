"""

    Safe Deployment library aims to create a sweet way to deploy on EC2 instances.
    The process is:
        * Check that every instances in the Load Balancer are in service and are enought to perform the safe deployment.
        * Split the instances list according the deployment type choose(1by1/25%/50%).
        * Before begin to deploy on a part of the instances list, remove them from their Load Balancer(Haproxy or ELB)
        * Wait a moment(depends on the connection draining value for the ELB and/or the custom value defines in Ghost)
        * Launch the standard deployment process
        * Wait a moment(depends on the custom value defines in Ghost)
        * Add the updated instances in their Load Balancer.
        * Wait until instance become healthly.
        * Do the same process for the next parts of the instances list.
    This library works with one or more Load Balancers per Autoscaling Group.

    For AutoScaling Group with one or more Haproxy as Load Balancer, the safe deployment process works with Hapi only:
    https://bitbucket.org/mattboret/hapi

"""
from elb import get_elb_instance_status_autoscaling_group, get_connection_draining_value, register_instance_from_elb
from ghost_tools import GCallException
from ghost_tools import check_autoscale_exists, get_autoscaling_group_and_processes_to_suspend, suspend_autoscaling_group_processes, launch_deploy, find_ec2_running_instances
import time
import haproxy
import boto.ec2.autoscale
import boto.ec2.elb


class SafeDeployment():
    """ Class which will manage the safe deployment process """

    def __init__(self, app, module, hosts_list, log_file, safe_infos, fabric_exec_strategy,  as_name, region):
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
        self.logger = log_file
        self.fab_exec_strategy = fabric_exec_strategy
        self.safe_infos = safe_infos
        self.as_name = as_name
        self.region = region
        self.as_conn = boto.ec2.autoscale.connect_to_region(region)
        self.elb_conn = boto.ec2.elb.connect_to_region(region)

    def split_hosts_list(self, split_type):
        """ Return a list of multiple hosts list for the safe deployment.

            :param hosts_list:     list:    Instances private IPs.
            :param split_type:     string:  The way to split the hosts list(1by1/25%/50%).
            :return                list:    Multiple hosts list or raise an Exception is the safe
                                            deployment process cannot be perform.
        """
        slice_per = {'1by1': 1,'25%': int(len(self.hosts_list)/4), '50%': int(len(self.hosts_list)/2)}
        if split_type not in slice_per.keys():
            self.logger("Split type {1} not currently supported. Only 1by1,25% or 25% are supported" .format(split_type))
            raise GCallException("Cannot continue, invalid split type for the safe deployment process")
        elif (len(self.hosts_list < 4) and split_type == '25%') or (len(self.hosts_list < 2) and split_type == '50%'):
            self.logger("Not enough instances to perform safe deployment. Number of instances: {0} for safe deployment type: {1}" .format(len(self.hosts_list), split_type))
            raise GCallException("Cannot continue, not enought instances to perform the safe deployment")
        else:
            n = max(1,slice_per[split_type])
            return [self.hosts_list[i:i + n] for i in range(0, len(self.hosts_list), n)]

    def elb_safe_deployment(self, instances_list):
        """ Manage the safe deployment process for the ELB.

            :param instances_list  list:  list of instances on which to deploy.
            :return                True if operation successed or raise an Exception.
        """
        elb_instances = get_elb_instance_status_autoscaling_group(self.elb_conn, self.as_name, self.region, self.as_conn)
        if len(set([len(i) for i in elb_instances.values()])) and not len([i for i in elb_instances.values() if 'outofservice' in i.values()]):
            deregister_instance_from_elb(self.elb_conn, elb_instances.keys(), elb_instances[elb_instances.keys()[0]].keys())
            wait_before_deploy = int(get_connection_draining_value(self.elb_conn, elb_instances.keys())) + int(self.safe_infos['wait_before_deploy'])
            self.logger('Waiting {0}s: The connection draining time more the custom value set for wait_before_deploy' .format(wait_before_deploy))
            time.sleep(wait_before_deploy)
            launch_deploy(self.app, self.module, ','.join([host['private_ip_address'] for host in instances_list]), self.fab_exec_strategy, self.logger)
            time.sleep(int(self.safe_infos['wait_after_deploy']))
            register_instance_from_elb(self.elb_conn, elb_instances.keys(), elb_instances[elb_instances.keys()[0]].keys())
            while len([i for i in get_elb_instance_status_autoscaling_group(self.elb_conn, self.as_name, self.region, self.as_conn).values() if 'outofservice' in i.values()]):
                self.logger('Waiting 10s because the instance is not in service in the ELB')
                time.sleep(10)
            self.logger('Instances: {0} have been deployed and are registered in their ELB' .format(str(instances_list)))
            return True
        else:
            raise GCallException('Cannot continue because there is an instance in out of service state or if the \
                                 AutoScaling Group has multiple ELBs it seems they haven\'t the same instances in their pool')

    def haproxy_configuration_validation(self, hapi, ha_urls):
        """ Check that every Haproxy have the same configuration.

            :param   hapi     Class object of the Haproxy lib.
            :param   ha_urls  list  A list of Haproxy URL.
            :return           Boolean:  True if all configurations are equal, False otherwise.
        """
        ha_confs = []
        for ha_url in ha_urls:
            ha_confs.append(self.hapi.get_haproxy_conf(ha_url))
        return hapi.check_haproxy_conf(ha_confs)


    def haproxy_safe_deployment(self, instances_list):
        """ Manage the safe deployment process for the Haproxy.

            :param  instances_list  list: Instances on which to deploy.
            :return                 True if operation successed or raise an Exception.
        """
        lb_infos = find_ec2_running_instances(self.safe_infos['app_id_ha'], app_env, 'loadbalancer', app_region)
        if lb_infos:
            hapi = haproxy.get_Haproxyapi(lb_infos)
            ha_urls = hapi.get_haproxy_urls()
            if not self.haproxy_configuration_validation(hapi, ha_urls):
                raise GCallException('Cannot initialize the safe deployment process because there is differences in the Haproxy \
                                    configuration files between the instances: {0}' .format(lb_infos))
            if not hapi.change_instance_state('disabledserver', self.safe_infos['ha_backend'], instances_list):
                raise GCallException('Cannot disabled some instances: {0} in {1}. Deployment aborded' .format(instances_list, lb_infos))
            time.sleep(int(self.safe_infos['wait_before_deploy']))
            launch_deploy(self.app, self.module, ','.join([host['private_ip_address'] for host in instances_list]), self.fab_exec_strategy, self.logger)
            time.sleep(int(self.safe_infos['wait_after_deploy']))
            if not hapi.change_instance_state('enabledserver', self.safe_infos['ha_backend'], instances_list):
                raise GCallException('Cannot enabled some instances: {0} in {1}. Deployment aborded' .format(instances_list, lb_infos))
            if not self.haproxy_configuration_validation(hapi, ha_urls):
                raise GCallException('Error in the post safe deployment process because there is differences in the Haproxy \
                                    configuration files between the instances: {0}. Instances: {1} have been deployed but not well enable' .format(lb_infos, instances_list))
            if not hapi.check_all_instances_enable(self.safe_infos['ha_backend'], hapi.get_haproxy_conf(ha_urls[0])):
                raise GCallException('Error in the post safe deployment process because some instances are disable or down in the Haproxy: {0}.' .format(lb_infos, instances_list))
            self.logger('Instances: {0} have been deployed and are registered in their Haproxy' .format(str(instances_list)))
            return True
        else:
            raise GCallException('Cannot continue because no Haproxy found with the parameters: app_id_ha: {0}, app_env: {1},\
                                 app_region: {2}' .format(self.safe_infos['app_id_ha'], app_env, 'loadbalancer', app_region))


    def safe_manager(self):
        """  Global manager for the safe deployment process.

            :return True if operation succeed otherwise an Exception will be raised.
        """
        for host_group in self.split_hosts_list(self.hosts_list, self.safe_infos['type']):
            if self.safe_infos['load_balancer_type'] == 'elb':
                self.elb_safe_deployment(host_group)
            else:
                self.haproxy_safe_deployment(host_group)
        return True
