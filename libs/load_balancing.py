from ghost_log import log
from libs.autoscaling import get_autoscaling_group_object

LB_TYPE_AWS_CLB = 'elb'
LB_TYPE_AWS_ALB = 'alb'


def get_lb_manager(cloud_connection, region, lb_type):
    """
    Returns a Load Balancer Manager depending on parameters
    :param cloud_connection: ACloudConnection: Connection to cloud provider
    :param region: string: cloud provider region for connection
    :param lb_type: string: type of load balancer for this provider
    :return: LoadBalancersManager
    """
    if lb_type == LB_TYPE_AWS_ALB:
        return AwsAlbManager(cloud_connection, region)
    if lb_type == LB_TYPE_AWS_CLB:
        return AwsClbManager(cloud_connection, region)
    raise ValueError("Unknown load balancer type")


class LoadBalancerItem(object):
    def __init__(self, data):
        self._data = data

    def __getattr__(self, item):
        return self._data[item]

    def __getitem__(self, item):
        return self._data[item]


class LoadBalancersManager(object):
    def __init__(self, cloud_connection, region):
        self.cloud_connection = cloud_connection
        self.region = region

    def configure_health_check(self, elb_name, interval, timeout, unhealthy_threshold, healthy_threshold,
                               target=None, protocol=None, port=None, path=None):
        """
            Configures the HealthCheck value
            :param elb_name: string: resource name
            :param interval: int: health check interval
            :param timeout: int: health check timeout
            :param unhealthy_threshold: string:
            :param healthy_threshold: string:
            :param target: string
            :param protocol: string:
            :param port: int:
            :param path: string:
        """
        raise NotImplementedError()

    def get_by_name(self, elb_name):
        """
            :return the found ELB object
        """
        raise NotImplementedError()

    def get_dns_name(self, elb_name):
        """ Return the DNS name for the passed ELB

            :param  elb_name:  string: The name of the Elastic Load Balancer.
            :return string
        """
        raise NotImplementedError()

    def get_from_autoscale(self, as_name):
        """ Return a list of ELB names defined in
            the Autoscaling Group in parameter.

            :param  as_name:  string: The Autoscaling Group name.
            :return  a list of ELB names.
        """
        raise NotImplementedError()

    def copy(self, elb_name, source_elb_name, special_tag, log_file):
        """ Copy an existing ELB, currently copies basic configuration
            (Subnets, SGs, first listener), health check and tags.

            :param elb_name: string: created ELB name
            :param source_elb_name: string: source ELB name
            :param special_tag: dict: a tag to add to the new lb
            :param log_file: string: log file
            :return created ELB endpoint
        """
        raise NotImplementedError()

    def destroy(self, elb_name, log_file):
        """ Destroy the specified ELB

            :param  elb_name:  string: The name of the Elastic Load Balancer.
            :param  log_file: string: log file
        """
        raise NotImplementedError()

    def register_into_autoscale(self, as_name, elbs_to_deregister, elbs_to_register, log_file):
        """ Modify the AutoScale Group to set the list of ELB to use

        :param  as_name:  string: string of the autoscaling group name.
        :param  elbs_to_deregister:  list: The name of the Elastic Load Balancers.
        :param  elbs_to_register:  list: The name of the Elastic Load Balancers.
        :param  log_file: string: The log file
        :return boolean(True if succeed otherwise False)
        """
        raise NotImplementedError()

    def get_instance_status_autoscaling_group(self, as_group):
        """ Return a dict of instance ids as key and their status as value per elb.

            :param  as_group: string of the autoscaling group name.
            :return dict(ex: {'elb_XXX1':{'instance_id':'inservice/outofservice'}})
        """
        raise NotImplementedError()

    def get_instance_status(self, elb_names):
        """ Return a dict of instance ids as key and their status as value per elb.

            :param  elb_names: list: The name of the Elastic Load Balancers.
            :return dict(ex: {'elb_XXX1':{'instance_id':'inservice/outofservice'}})
        """
        raise NotImplementedError()

    def deregister_instance_from_elb(self, elb_names, hosts_id_list, log_file):
        """ Registrer one or multiple instances in the ELB pool.

            :param  elb_names: list The name of the Elastic Load Balancers.
            :param  hosts_id_list: list of instances ID to add to the ELB pool.
            :param  log_file:  string  The log file
            :return boolean(True if succeed otherwise False)
        """
        raise NotImplementedError()

    def deregister_all_instances_from_elb(self, elbs_with_instances, log_file):
        """ Deregistrer one or multiple instances in the ELB pool.

            :param  elbs_with_instances: list The name of the Elastic Load Balancers, and all instances in one of them.
                    (dict(ex: {'elb_XXX1':{'instance_id':'inservice/outofservice'}}))
            :param  log_file:  string  The log file
            :return boolean(True if succeed otherwise False)
        """
        raise NotImplementedError()

    def register_instance_from_elb(self, elb_names, hosts_id_list, log_file):
        """ Registrer one or multiple instances in the ELB pool.

            :param  elb_names: list The name of the Elastic Load Balancers.
            :param  hosts_id_list: list of instances ID to add to the ELB pool.
            :param  log_file:  string  The log file
            :return boolean(True if succeed otherwise False)
        """
        raise NotImplementedError()

    def register_all_instances_to_elb(self, elb_names, instances, log_file):
        """ Registrer one or multiple instances in the ELB pool.

            :param  elb_names: list The name of the Elastic Load Balancers.
            :param  instances: list The name of the Elastic Load Balancers, and all instances in one of them.
                    (dict(ex: {'elb_XXX1':{'instance_id':'inservice/outofservice'}}))
            :param  log_file:  string  The log file
            :return boolean(True if succeed otherwise False)
        """
        raise NotImplementedError()

    def get_connection_draining_value(self, elb_names):
        """ Return the biggest connection draining value for the list of elb in parameters.

            :param  elb_names: list The name of the Elastic Load Balancers.
            :return  int  The value in seconds of the connection draining.
        """
        raise NotImplementedError()

    def get_target_groups_from_autoscale(self, as_name):
        """ Return a list of ALB target groups ARN defined in
            the Autoscaling Group in parameter.

            :param  as_name:  string: The Autoscaling Group name.
            :return  a list of ALB target groups ARN.
        """
        raise NotImplementedError()

    def get_target_status_autoscaling_group(self, as_group):
        """ Return a dict of instance ids as key and their status as value per alb target group.

            :param  as_group: string of the autoscaling group name.
            :return dict(ex: {'alb_XXX1':{'instance_id':'healthy/unhealthy'}})
        """


class AwsElbManager(LoadBalancersManager):
    def __init__(self, cloud_connection, region):
        super(AwsElbManager, self).__init__(cloud_connection, region)
        self._connections = {'boto2': {}, 'boto3': {}}

    def _get_connection(self, services, boto2_compat=False):
        boto_version = 'boto2' if boto2_compat else 'boto3'
        cache_key = str(services)
        try:
            return self._connections[boto_version][cache_key]
        except KeyError:
            conn = self.cloud_connection.get_connection(
                self.region, services, boto_version=boto_version)
            self._connections[boto_version][cache_key] = conn
            return conn

    def _get_as_connection(self):
        return self._get_connection(['autoscaling'])


class AwsClbManager(AwsElbManager):
    def _get_elb_connection(self, boto2_compat=False):
        if boto2_compat:
            return self._get_connection(['ec2', 'elb'], boto2_compat=True)
        else:
            return self._get_connection(['elb'])

    def get_by_name(self, elb_name):
        elb_conn3 = self._get_elb_connection()
        try:
            elb = elb_conn3.describe_load_balancers(
                LoadBalancerNames=[elb_name])['LoadBalancerDescriptions'][0]
            return LoadBalancerItem(elb)
        except Exception:
            return None

    def get_dns_name(self, elb_name):
        return self.get_by_name(elb_name).DNSName

    def register_instance_from_elb(self, elb_names, hosts_id_list, log_file):
        try:
            elb_conn = self._get_elb_connection()
            for elb_name in elb_names:
                if not elb_conn.register_instances(elb_name, hosts_id_list).status:
                    log("Failed to register instances {0} in the ELB {1}".format(str(hosts_id_list), elb_name),
                        log_file)
                    raise Exception()
                else:
                    log("Instances {0} well registered in the ELB {1}".format(str(hosts_id_list), elb_name), log_file)
            return True
        except Exception as e:
            log("Exception during register operation: {0}".format(str(e)), log_file)
            raise

    def deregister_instance_from_elb(self, elb_names, hosts_id_list, log_file):
        try:
            elb_conn = self._get_elb_connection(boto2_compat=True)
            for elb_name in elb_names:
                if not elb_conn.deregister_instances(elb_name, hosts_id_list).status:
                    log("Failed to deregister instances {0} in the ELB {1}".format(str(hosts_id_list), elb_name),
                        log_file)
                    raise Exception()
                else:
                    log("Instances {0} well deregistered in the ELB {1}" .format(str(hosts_id_list), elb_name),
                        log_file)
            return True
        except Exception as e:
            log("Exception during deregister operation: {0}" .format(str(e)), log_file)
            raise

    def deregister_all_instances_from_elb(self, elbs_with_instances, log_file):
        try:
            elb_conn = self._get_elb_connection(boto2_compat=True)
            for elb_name, elb_instances in elbs_with_instances.items():
                # sorted is only used in order to have predictable method calls for test cases
                instance_names = sorted(elb_instances.keys())
                if not elb_conn.deregister_instances(elb_name, instance_names).status:
                    log("Failed to deregister instances {0} in the ELB {1}".format(str(instance_names), elb_name),
                        log_file)
                    raise Exception()
                else:
                    log("Instances {0} well deregistered in the ELB {1}".format(str(instance_names), elb_name),
                        log_file)
            return True
        except Exception as e:
            log("Exception during deregister operation: {0}".format(str(e)), log_file)
            raise

    def register_all_instances_to_elb(self, elb_names, instances, log_file):
        try:
            elb_conn = self._get_elb_connection(boto2_compat=True)
            for elb_name in elb_names:
                for unused_elb_name, elb_instances in instances.items():
                    # sorted is only used in order to have predictable method calls for test cases
                    instance_names = sorted(elb_instances.keys())
                    if not elb_conn.register_instances(elb_name, instance_names).status:
                        log("Failed to register instances {0} in the ELB {1}".format(str(instance_names), elb_name),
                            log_file)
                        raise Exception()
                    else:
                        log("Instances {0} well registered in the ELB {1}".format(str(instance_names), elb_name),
                            log_file)
            return True
        except Exception as e:
            log("Exception during register operation: {0}".format(str(e)), log_file)
            raise

    def get_instance_status(self, elb_names):
        elb_conn = self._get_elb_connection(boto2_compat=True)
        as_instance_status = {}
        for elb in elb_names:
            as_instance_status[elb] = {}
            for instance in elb_conn.describe_instance_health(elb):
                as_instance_status[elb][
                    instance.instance_id] = "inservice" if instance.state.lower() == "inservice" else "outofservice"
        return as_instance_status

    def register_into_autoscale(self, as_name, elbs_to_deregister, elbs_to_register, log_file):
        as_conn3 = self._get_as_connection()
        try:
            if elbs_to_deregister and len(elbs_to_deregister) > 0:
                as_conn3.detach_load_balancers(AutoScalingGroupName=as_name, LoadBalancerNames=elbs_to_deregister)
            if elbs_to_register and len(elbs_to_register) > 0:
                as_conn3.attach_load_balancers(AutoScalingGroupName=as_name, LoadBalancerNames=elbs_to_register)
        except Exception as e:
            log("Exception during register ELB operation into ASG: {0}".format(str(e)), log_file)
            raise

    def get_from_autoscale(self, as_name):
        as_conn = self._get_as_connection()
        if not as_name:  # prevent to get all ASG and use first one...
            return []
        asg = get_autoscaling_group_object(as_conn, as_name)
        return asg['LoadBalancerNames'] if asg else []

    def get_instance_status_autoscaling_group(self, as_group):
        elb_conn = self._get_elb_connection(boto2_compat=True)
        as_instance_status = {}
        for elb in self.get_from_autoscale(as_group):
            as_instance_status[elb] = {}
            for instance in elb_conn.describe_instance_health(elb):
                as_instance_status[elb][
                    instance.instance_id] = "inservice" if instance.state.lower() == "inservice" else "outofservice"
        return as_instance_status

    def copy(self, elb_name, source_elb_name, special_tag, log_file):
        elb_conn3 = self._get_elb_connection()
        dest_elb = self.get_by_name(elb_name)
        if dest_elb:
            log("  INFO: ELB {0} already available, no copy needed".format(elb_name), log_file)
            return dest_elb['DNSName']
        source_elb = self.get_by_name(source_elb_name)
        source_elb_listener = source_elb['ListenerDescriptions'][0]['Listener']
        source_elb_tags = elb_conn3.describe_tags(
            LoadBalancerNames=[source_elb_name]
        )['TagDescriptions'][0]['Tags']
        source_elb_tags.append(special_tag)
        source_elb_attributes = elb_conn3.describe_load_balancer_attributes(
            LoadBalancerName=source_elb_name
        )['LoadBalancerAttributes']
        dest_elb_listener = {
            'Protocol': source_elb_listener['Protocol'],
            'LoadBalancerPort': source_elb_listener['LoadBalancerPort'],
            'InstanceProtocol': source_elb_listener['InstanceProtocol'],
            'InstancePort': source_elb_listener['InstancePort']
        }

        # Check if listener needs SSLCertificate
        if 'SSLCertificateId' in source_elb_listener:
            dest_elb_listener['SSLCertificateId'] = source_elb_listener['SSLCertificateId']

        # Create ELB
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

        # Update ELB attributes
        elb_conn3.modify_load_balancer_attributes(
            LoadBalancerName=elb_name,
            LoadBalancerAttributes=source_elb_attributes
        )

        return response['DNSName']

    def destroy(self, elb_name, log_file):
        elb_conn3 = self._get_elb_connection()
        log("  INFO: Destroying ELB {0}".format(elb_name), log_file)
        elb_conn3.delete_load_balancer(LoadBalancerName=elb_name)

    def get_connection_draining_value(self, elb_names):
        elb_conn = self._get_elb_connection(boto2_compat=True)
        return max([elb_conn.get_all_lb_attributes(elb).connection_draining.timeout for elb in elb_names])

    def configure_health_check(self, elb_name, interval, timeout, unhealthy_threshold, healthy_threshold, target=None,
                               protocol=None, port=None, path=None):
        elb_conn3 = self._get_elb_connection()
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


class AwsAlbManager(AwsElbManager):
    def _get_alb_connection(self):
        return self._get_connection(['alb'])

    def get_dns_name(self, elb_name):
        pass

    def register_instance_from_elb(self, alb_tgs, hosts_id_list, log_file):
        try:
            alb_conn = self._get_alb_connection()
            for alb_tg_arn in alb_tgs:
                if len(alb_conn.register_targets(TargetGroupArn=alb_tg_arn, Targets=hosts_id_list)) != len(
                        hosts_id_list):
                    log("Failed to register instances {0} in the ALB {1}".format(str(hosts_id_list), alb_tg_arn),
                        log_file)
                    raise Exception()
                else:
                    log("Instances {0} well registered in the ALB {1}".format(str(hosts_id_list), alb_tg_arn), log_file)
            return True
        except Exception as e:
            log("Exception during deregister operation: {0}".format(str(e)), log_file)
            raise

    def register_all_instances_to_elb(self, elb_names, instances, log_file):
        pass

    def destroy(self, elb_name, log_file):
        pass

    def get_instance_status(self, elb_names):
        pass

    def register_into_autoscale(self, as_name, elbs_to_deregister, elbs_to_register, log_file):
        pass

    def get_from_autoscale(self, as_name):
        pass

    def get_instance_status_autoscaling_group(self, as_group):
        pass

    def configure_health_check(self, elb_name, interval, timeout, unhealthy_threshold, healthy_threshold, target=None,
                               protocol=None, port=None, path=None):
        alb_conn3 = self._get_alb_connection()
        response = alb_conn3.modify_target_group(
            TargetGroupArn=target,
            HealthCheckProtocol=protocol,
            HealthCheckPort=port,
            HealthCheckPath=path,
            HealthCheckIntervalSeconds=interval,
            HealthCheckTimeoutSeconds=timeout,
            HealthyThresholdCount=healthy_threshold,
            UnhealthyThresholdCount=unhealthy_threshold
        )
        return response

    def get_by_name(self, elb_name):
        alb_conn3 = self._get_alb_connection()
        alb = alb_conn3.describe_load_balancers(
            Names=[elb_name],
            PageSize=1
        )['LoadBalancers'][0]
        return alb

    def copy(self, elb_name, source_elb_name, special_tag, log_file):
        pass

    def deregister_all_instances_from_elb(self, elbs_with_instances, log_file):
        pass

    def get_connection_draining_value(self, elb_names):
        alb_conn = self._get_alb_connection()
        values = []
        for alb_tg in elb_names:
            attrs = alb_conn.describe_target_group_attributes(TargetGroupArn=alb_tg)['Attributes']
            for at in attrs:
                if at['Key'] == 'deregistration_delay.timeout_seconds':
                    values.append(int(at['Value']))
        return max(values)

    def deregister_instance_from_elb(self, alb_tgs, hosts_id_list, log_file):
        try:
            alb_conn = self._get_alb_connection()
            for alb_tg_arn in alb_tgs:
                if len(alb_conn.deregister_targets(TargetGroupArn=alb_tg_arn, Targets=hosts_id_list)) != len(
                        hosts_id_list):
                    log("Failed to deregister instances {0} in the ALB {1}".format(str(hosts_id_list), alb_tg_arn),
                        log_file)
                    raise Exception()
                else:
                    log("Instances {0} well deregistered in the ALB {1}".format(str(hosts_id_list), alb_tg_arn),
                        log_file)
            return True
        except Exception as e:
            log("Exception during deregister operation: {0}".format(str(e)), log_file)
            raise

    def get_target_groups_from_autoscale(self, as_name):
        as_conn = self._get_as_connection()
        if not as_name:  # prevent to get all ASG and use first one...
            return []
        asg = get_autoscaling_group_object(as_conn, as_name)
        return asg['TargetGroupARNs'] if asg else []

    def get_target_status_autoscaling_group(self, as_group):
        alb_conn = self._get_alb_connection()
        as_instance_status = {}
        for tg_arn in self.get_target_groups_from_autoscale(as_group):
            as_instance_status[tg_arn] = {}
            for target_health in alb_conn.describe_target_health(TargetGroupArn=tg_arn)['TargetHealthDescriptions']:
                target_id = target_health['Target']['Id']
                target_state = target_health['TargetHealth']['State']
                as_instance_status[tg_arn][target_id] = "healthy" if target_state.lower() == "healthy" else "unhealthy"
        return as_instance_status
