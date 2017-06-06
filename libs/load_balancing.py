import itertools
from botocore.exceptions import ClientError

import ghost_aws
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


class LoadBalancerManagerException(BaseException):
    pass


class LoadBalancerItem(object):
    def __init__(self, data):
        self._data = data

    def _get(self, item):
        value = self._data.get(item, KeyError)
        if item.lower() == 'name':
            value = self._data.get('LoadBalancerName', self._data.get('Name', value))
        if item.lower() == 'id':
            value = self._data.get('LoadBalancerArn', self._data.get('Name', value))
        if value == KeyError:
            raise KeyError('Invalid key')
        return value

    def __getattr__(self, item):
        return self._get(item)

    def __getitem__(self, item):
        return self._get(item)


class LoadBalancersManager(object):
    def __init__(self, cloud_connection, region):
        self.cloud_connection = cloud_connection
        self.region = region

    def get_health_check(self, elb_name):
        """
            returns the health check configuration as dict like {'interval': '',
                      'timeout': '', 'unhealthy_threshold': '', 'healthy_threshold': '',
                      'protocol': '', 'port': '', 'path': '', 'target': ''}
            :param elb_name: string: resource name
            :returns dict:
        """
        raise NotImplementedError()

    def configure_health_check(self, elb_name, interval=None, timeout=None, unhealthy_threshold=None,
                               healthy_threshold=None, protocol=None, port=None, path=None, target=None):
        """
            Configures the HealthCheck value
            :param elb_name: string: resource name
            :param interval: int: health check interval
            :param timeout: int: health check timeout
            :param unhealthy_threshold: string:
            :param healthy_threshold: string:
            :param protocol: string:
            :param port: int:
            :param path: string:
            :param target: string:
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

    def list_from_autoscale(self, as_name, log_file, filter_tag=None):
        """ Return a list of ELB names defined in
            the Autoscaling Group in parameter.

            :param log_file:
            :param  as_name:  string: The Autoscaling Group name.
            :param  filter_tag: dict: A dict with a unique value that will be used as a filter for tags
            :return  a list of ELB names.
        """
        raise NotImplementedError()

    def copy(self, elb_name, source_elb_name, additional_tags, log_file):
        """ Copy an existing ELB, currently copies basic configuration
            (Subnets, SGs, first listener), health check and tags.

            :param elb_name: string: created ELB name
            :param source_elb_name: string: source ELB name
            :param additional_tags: dict: tags to add to the new lb
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

    def get_instance_status_autoscaling_group(self, as_group, log_file):
        """ Return a dict of instance ids as key and their status as value per elb.

            :param log_file:
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
        raise NotImplementedError()


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
    HEALTHCHECK_PARAMS_MAPPING = {
        'interval': 'Interval',
        'timeout': 'Timeout',
        'unhealthy_threshold': 'UnhealthyThreshold',
        'healthy_threshold': 'HealthyThreshold',
        'target': 'Target',
        'protocol': None,
        'port': None,
        'path': None,
    }

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

    def list_from_autoscale(self, as_name, log_file, filter_tag=None):
        if filter_tag and len(filter_tag) > 1:
            raise LoadBalancerManagerException('Filter can only take one tag')
        as_conn = self._get_as_connection()
        elb_conn = self._get_elb_connection()
        if not as_name:  # prevent to get all ASG and use first one...
            return []
        asg = get_autoscaling_group_object(as_conn, as_name)
        lb_names = asg['LoadBalancerNames'] if asg else []
        if filter_tag and len(lb_names) > 0:
            filtered_lb_names = []
            for lb_tags in elb_conn.describe_tags(LoadBalancerNames=lb_names)['TagDescriptions']:
                for tag in lb_tags['Tags']:
                    if {tag['Key']: tag['Value']} == filter_tag:
                        filtered_lb_names.append(lb_tags['LoadBalancerName'])
                        break
            return filtered_lb_names
        return lb_names

    def get_instance_status_autoscaling_group(self, as_group, log_file):
        elb_conn = self._get_elb_connection(boto2_compat=True)
        as_instance_status = {}
        for elb in self.list_from_autoscale(as_group, log_file):
            as_instance_status[elb] = {}
            for instance in elb_conn.describe_instance_health(elb):
                as_instance_status[elb][
                    instance.instance_id] = "inservice" if instance.state.lower() == "inservice" else "outofservice"
        return as_instance_status

    def copy(self, elb_name, source_elb_name, additional_tags, log_file):
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
            Tags=source_elb_tags + ghost_aws.dict_to_aws_tags(additional_tags)
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

    def get_health_check(self, elb_name):
        elb = self.get_by_name(elb_name)
        return {k: elb['HealthCheck'].get(v) for k, v in self.HEALTHCHECK_PARAMS_MAPPING.items()}

    def configure_health_check(self, elb_name, interval=None, timeout=None, unhealthy_threshold=None,
                               healthy_threshold=None, protocol=None, port=None, path=None, target=None):
        elb_conn3 = self._get_elb_connection()
        cur_health_check = self.get_by_name(elb_name)['HealthCheck']

        func_params = locals()
        cur_health_check.update({v: func_params[p]
                                 for p, v in self.HEALTHCHECK_PARAMS_MAPPING.items() if func_params.get(p, None)})
        elb_conn3.configure_health_check(
            LoadBalancerName=elb_name,
            HealthCheck=cur_health_check
        )


class AwsAlbManager(AwsElbManager):
    HEALTHCHECK_PARAMS_MAPPING = {
        'interval': 'HealthCheckIntervalSeconds',
        'timeout': 'HealthCheckTimeoutSeconds',
        'unhealthy_threshold': 'UnhealthyThresholdCount',
        'healthy_threshold': 'HealthyThresholdCount',
        'protocol': 'HealthCheckProtocol',
        'port': 'HealthCheckPort',
        'path': 'HealthCheckPath',
        'target': None,
    }

    def _get_alb_connection(self):
        return self._get_connection(['elbv2'])

    def _get_targetgroup_arns_from_autoscale(self, as_name):
        conn = self._get_as_connection()
        try:
            lbtg = conn.describe_load_balancer_target_groups(AutoScalingGroupName=as_name)
            return [tg['LoadBalancerTargetGroupARN'] for tg in lbtg['LoadBalancerTargetGroups']]
        except (ClientError, KeyError):
            return []

    def _get_targetgroup_arns_from_alb(self, alb_arn):
        return [tg['TargetGroupArn']
                for tg in self._get_alb_connection().describe_target_groups(LoadBalancerArn=alb_arn)['TargetGroups']]

    def get_by_name(self, elb_name):
        alb_conn3 = self._get_alb_connection()
        try:
            alb = alb_conn3.describe_load_balancers(
                Names=[elb_name]
            )['LoadBalancers'][0]
            return LoadBalancerItem(alb)
        except Exception as e:
            if e.__class__.__name__ == 'LoadBalancerNotFoundException':
                return None
            raise e

    def get_dns_name(self, elb_name):
        return self.get_by_name(elb_name).DNSName

    def get_connection_draining_value(self, elb_names):
        alb_conn = self._get_alb_connection()
        values = []
        alb_arns = ([alb['LoadBalancerArn']
                    for alb in alb_conn.describe_load_balancers(Names=elb_names)['LoadBalancers']])
        for alb_arn in alb_arns:
            for tg_arn in self._get_targetgroup_arns_from_alb(alb_arn):
                attrs = alb_conn.describe_target_group_attributes(TargetGroupArn=tg_arn)['Attributes']
                for at in attrs:
                    if at['Key'] == 'deregistration_delay.timeout_seconds':
                        values.append(int(at['Value']))
                        break
        return max(values)

    def copy(self, elb_name, source_elb_name, additional_tags, log_file):
        alb_conn3 = self._get_alb_connection()
        dest_alb = self.get_by_name(elb_name)
        if dest_alb:
            log("  INFO: ALB {0} already available, no copy needed".format(elb_name), log_file)
            return dest_alb['DNSName']
        source_alb = self.get_by_name(source_elb_name)
        source_alb_arn = source_alb['LoadBalancerArn']

        source_alb_tags = alb_conn3.describe_tags(
            ResourceArns=[source_alb_arn]
        )['TagDescriptions'][0]['Tags']

        source_alb_attributes = alb_conn3.describe_load_balancer_attributes(
            LoadBalancerArn=source_alb_arn
        )['Attributes']

        # Create ALB
        dest_alb = alb_conn3.create_load_balancer(
            Name=elb_name,
            Subnets=[az['SubnetId'] for az in source_alb['AvailabilityZones']],
            SecurityGroups=source_alb['SecurityGroups'],
            Scheme=source_alb['Scheme'],
            Tags=source_alb_tags + ghost_aws.dict_to_aws_tags(additional_tags)
        )['LoadBalancers'][0]
        dest_alb_arn = dest_alb['LoadBalancerArn']

        # Update ALB attributes
        alb_conn3.modify_load_balancer_attributes(
            LoadBalancerArn=dest_alb_arn,
            Attributes=[attr for attr in source_alb_attributes if attr['Value'] != '']
        )

        # Copy target group
        source_tg_list = alb_conn3.describe_target_groups(LoadBalancerArn=source_alb_arn)['TargetGroups']
        if len(source_tg_list) > 1:
            raise LoadBalancerManagerException('Multiple target groups for an ALB is currently not supported')
        source_tg = source_tg_list[0]
        source_tg_arn = source_tg['TargetGroupArn']

        response = alb_conn3.create_target_group(
            Name='tg-{}'.format(elb_name)[:31],
            Protocol=source_tg['Protocol'],
            Port=source_tg['Port'],
            VpcId=source_tg['VpcId'],
            HealthCheckProtocol=source_tg['HealthCheckProtocol'],
            HealthCheckPort=source_tg['HealthCheckPort'],
            HealthCheckPath=source_tg['HealthCheckPath'],
            HealthCheckIntervalSeconds=source_tg['HealthCheckIntervalSeconds'],
            HealthCheckTimeoutSeconds=source_tg['HealthCheckTimeoutSeconds'],
            HealthyThresholdCount=source_tg['HealthyThresholdCount'],
            UnhealthyThresholdCount=source_tg['UnhealthyThresholdCount'],
            Matcher=source_tg['Matcher']
        )
        dest_tg_arn = response['TargetGroups'][0]['TargetGroupArn']
        alb_conn3.add_tags(ResourceArns=[dest_tg_arn],
                           Tags=ghost_aws.dict_to_aws_tags(additional_tags))

        # Creating listeners
        source_listeners = alb_conn3.describe_listeners(LoadBalancerArn=source_alb_arn)
        for listener in source_listeners['Listeners']:
            for action in listener['DefaultActions']:
                if action['TargetGroupArn'] == source_tg_arn:
                    action['TargetGroupArn'] = dest_tg_arn
            params = {
                'LoadBalancerArn': dest_alb_arn,
                'Protocol': listener['Protocol'],
                'Port': listener['Port'],
                'DefaultActions': listener['DefaultActions']
            }
            # Possibly non existent params, but None value is forbidden in API call
            for param in ['SslPolicy', 'Certificates']:
                if listener.get(param, None):
                    params[param] = listener[param]
            alb_conn3.create_listener(**params)

        return dest_alb['DNSName']

    def destroy(self, elb_name, log_file):
        alb_conn3 = self._get_alb_connection()

        alb = alb_conn3.describe_load_balancers(Names=[elb_name])['LoadBalancers'][0]
        alb_arn = alb['LoadBalancerArn']
        listeners_arns = [tg['ListenerArn']
                          for tg in alb_conn3.describe_listeners(LoadBalancerArn=alb_arn)['Listeners']]
        tg_arns = [tg['TargetGroupArn']
                   for tg in alb_conn3.describe_target_groups(LoadBalancerArn=alb_arn)['TargetGroups']]

        for arn in listeners_arns:
            log('Deleting LB Listener {}'.format(arn), log_file)
            alb_conn3.delete_listener(ListenerArn=arn)
        for arn in tg_arns:
            log('Deleting Target Group {}'.format(arn), log_file)
            alb_conn3.delete_target_group(TargetGroupArn=arn)
        log('Deleting ALB {}'.format(alb_arn), log_file)
        alb_conn3.delete_load_balancer(LoadBalancerArn=alb_arn)

    def _get_instance_status_from_alb(self, alb_arn):
        alb_conn = self._get_alb_connection()
        ret = {}
        for tg_arn in self._get_targetgroup_arns_from_alb(alb_arn):
            for target_health in alb_conn.describe_target_health(TargetGroupArn=tg_arn)['TargetHealthDescriptions']:
                # Accepting draining state in order to behave like CLB
                ret[target_health['Target']['Id']] = (
                    "inservice"
                    if target_health['TargetHealth']['State'].lower() in ("healthy", 'draining')
                    else "outofservice")
        return ret

    def get_instance_status(self, elb_names):
        alb_conn = self._get_alb_connection()
        albs = ({alb['LoadBalancerName']: alb['LoadBalancerArn']
                 for alb in alb_conn.describe_load_balancers(Names=elb_names)['LoadBalancers']})
        as_instance_status = {}
        for alb_name, alb_arn in albs.items():
            as_instance_status[alb_name] = self._get_instance_status_from_alb(alb_arn)
        return as_instance_status

    def get_instance_status_autoscaling_group(self, as_group, log_file):
        as_instance_status = {}
        for alb in self._list_objects_from_autoscale(as_group):
            as_instance_status[alb['LoadBalancerName']] = self._get_instance_status_from_alb(alb['LoadBalancerArn'])
        return as_instance_status

    def register_into_autoscale(self, as_name, elbs_to_deregister, elbs_to_register, log_file):
        elbs_to_deregister = elbs_to_deregister or []
        elbs_to_register = elbs_to_register or []
        as_conn3 = self._get_as_connection()
        try:
            for alb in elbs_to_register:
                alb = self.get_by_name(alb)
                source_tg_list = self._get_targetgroup_arns_from_alb(alb['LoadBalancerArn'])
                if len(source_tg_list) > 1:
                    raise LoadBalancerManagerException('Multiple target groups for an ALB is currently not supported')
                log('Attaching Target Group {0} to ASG {1}'.format(source_tg_list[0], as_name), log_file)
                as_conn3.attach_load_balancer_target_groups(
                    AutoScalingGroupName=as_name, TargetGroupARNs=[source_tg_list[0]])

            for alb in elbs_to_deregister:
                alb = self.get_by_name(alb)
                source_tg_list = self._get_targetgroup_arns_from_alb(alb['LoadBalancerArn'])
                if len(source_tg_list) > 1:
                    raise LoadBalancerManagerException('Multiple target groups for an ALB is currently not supported')
                log('Detaching Target Group {0} from ASG {1}'.format(source_tg_list[0], as_name), log_file)
                as_conn3.detach_load_balancer_target_groups(
                    AutoScalingGroupName=as_name, TargetGroupARNs=[source_tg_list[0]])
        except Exception as e:
            log("Exception during register ELB operation into ASG: {0}".format(str(e)), log_file)
            raise

    def _list_objects_from_autoscale(self, as_name, filter_tag=None):
        if filter_tag and len(filter_tag) > 1:
            raise LoadBalancerManagerException('Filter can only tag one tag')
        conn = self._get_alb_connection()
        tg_arns = self._get_targetgroup_arns_from_autoscale(as_name)
        if len(tg_arns) > 0:
            tg_list = conn.describe_target_groups(TargetGroupArns=tg_arns)
            lb_arns = list(itertools.chain(*(tg['LoadBalancerArns'] for tg in tg_list['TargetGroups'])))
            if filter_tag and len(lb_arns) > 0:
                filtered_arns = []
                for lb_tags in conn.describe_tags(ResourceArns=lb_arns)['TagDescriptions']:
                    for tag in lb_tags['Tags']:
                        if {tag['Key']: tag['Value']} == filter_tag:
                            filtered_arns.append(lb_tags['ResourceArn'])
                            break
                lb_arns = filtered_arns
            return conn.describe_load_balancers(LoadBalancerArns=lb_arns)['LoadBalancers']
        return []

    def list_from_autoscale(self, as_name, log_file, filter_tag=None):
        return [lb['LoadBalancerName'] for lb in self._list_objects_from_autoscale(as_name, filter_tag)]

    def get_health_check(self, elb_name):
        alb = self.get_by_name(elb_name)
        conn = self._get_alb_connection()
        tg_list = conn.describe_target_groups(LoadBalancerArn=alb['LoadBalancerArn'])['TargetGroups']
        if len(tg_list) > 1:
            raise LoadBalancerManagerException('Multiple target groups for an ALB is currently not supported')
        return {k: tg_list[0].get(v, None) for k, v in self.HEALTHCHECK_PARAMS_MAPPING.items()}

    def configure_health_check(self, elb_name, interval=None, timeout=None, unhealthy_threshold=None,
                               healthy_threshold=None, protocol=None, port=None, path=None, target=None):
        alb_conn3 = self._get_alb_connection()
        func_params = locals()
        params = {v: func_params[p] for p, v in self.HEALTHCHECK_PARAMS_MAPPING.items() if func_params.get(p, None)}
        for tg_arn in self._get_targetgroup_arns_from_alb(self.get_by_name(elb_name)['LoadBalancerArn']):
            params['TargetGroupArn'] = tg_arn
            response = alb_conn3.modify_target_group(**params)

    def register_all_instances_to_elb(self, elb_names, instances, log_file):
        try:
            alb_conn = self._get_alb_connection()
            albs = ({alb['LoadBalancerName']: alb['LoadBalancerArn']
                    for alb in alb_conn.describe_load_balancers(Names=elb_names)['LoadBalancers']})
            for alb_name, alb_arn in albs.items():
                tg_list = alb_conn.describe_target_groups(LoadBalancerArn=alb_arn)['TargetGroups']
                if len(tg_list) > 1:
                    raise LoadBalancerManagerException('Multiple target groups for an ALB is currently not supported')
                tg_arn = tg_list[0]['TargetGroupArn']
                for unused_elb_name, elb_instances in instances.items():
                    # sorted is only used in order to have predictable method calls for test cases
                    instance_names = sorted(elb_instances.keys())
                    try:
                        alb_conn.register_targets(TargetGroupArn=tg_arn,
                                                  Targets=[{'Id': name} for name in instance_names])
                        log("Instances {0} well registered in the ALB {1}".format(str(instance_names), alb_name),
                            log_file)
                    except Exception as e:
                        log("Failed to register instances {0} in the ALB {1} : {2}".format(
                            str(instance_names), alb_name, e.message), log_file)
                        raise
            return True
        except Exception as e:
            log("Exception during register operation: {0}".format(str(e)), log_file)
            raise

    def deregister_all_instances_from_elb(self, elbs_with_instances, log_file):
        try:
            alb_conn = self._get_alb_connection()
            albs = ({alb['LoadBalancerName']: alb['LoadBalancerArn']
                    for alb in alb_conn.describe_load_balancers(Names=elbs_with_instances.keys())['LoadBalancers']})
            for alb_name, alb_arn in albs.items():
                tg_list = alb_conn.describe_target_groups(LoadBalancerArn=alb_arn)['TargetGroups']
                if len(tg_list) > 1:
                    raise LoadBalancerManagerException('Multiple target groups for an ALB is currently not supported')
                tg_arn = tg_list[0]['TargetGroupArn']
                # sorted is only used in order to have predictable method calls for test cases
                instance_names = sorted(elbs_with_instances[alb_name].keys())
                try:
                    alb_conn.deregister_targets(TargetGroupArn=tg_arn,
                                                Targets=[{'Id': name} for name in instance_names])
                    log("Instances {0} well deregistered in the ALB {1}".format(str(instance_names), alb_name),
                        log_file)
                except Exception as e:
                    log("Failed to deregister instances {0} in the ALB {1} : {2}".format(
                        str(instance_names), alb_name, e.message), log_file)
                    raise
            return True
        except Exception as e:
            log("Exception during deregister operation: {0}".format(str(e)), log_file)
            raise

    def register_instance_from_elb(self, elb_names, hosts_id_list, log_file):
        try:
            alb_conn = self._get_alb_connection()
            albs = ({alb['LoadBalancerName']: alb['LoadBalancerArn']
                    for alb in alb_conn.describe_load_balancers(Names=elb_names)['LoadBalancers']})
            for alb_name, alb_arn in albs.items():
                for alb_tg_arn in self._get_targetgroup_arns_from_alb(alb_arn):
                    alb_conn.register_targets(
                        TargetGroupArn=alb_tg_arn,
                        Targets=[{'Id': host_id} for host_id in hosts_id_list])
                    log("Instances {0} well registered in the ALB {1}".format(str(hosts_id_list), alb_name), log_file)
            return True
        except Exception as e:
            log("Exception during deregister operation: {0}".format(str(e)), log_file)
            raise

    def deregister_instance_from_elb(self, elb_names, hosts_id_list, log_file):
        try:
            alb_conn = self._get_alb_connection()
            albs = ({alb['LoadBalancerName']: alb['LoadBalancerArn']
                    for alb in alb_conn.describe_load_balancers(Names=elb_names)['LoadBalancers']})
            for alb_name, alb_arn in albs.items():
                for alb_tg_arn in self._get_targetgroup_arns_from_alb(alb_arn):
                    alb_conn.deregister_targets(
                        TargetGroupArn=alb_tg_arn,
                        Targets=[{'Id': host_id} for host_id in hosts_id_list])
                    log("Instances {0} well deregistered in the ALB {1}".format(str(hosts_id_list), alb_name), log_file)
            return True
        except Exception as e:
            log("Exception during deregister operation: {0}".format(str(e)), log_file)
            raise

    def get_target_groups_from_autoscale(self, as_name):
        return self._get_targetgroup_arns_from_autoscale(as_name)

    def get_target_status_autoscaling_group(self, as_group):
        alb_conn = self._get_alb_connection()
        as_instance_status = {}
        for tg_arn in self._get_targetgroup_arns_from_autoscale(as_group):
            as_instance_status[tg_arn] = {}
            for target_health in alb_conn.describe_target_health(TargetGroupArn=tg_arn)['TargetHealthDescriptions']:
                target_id = target_health['Target']['Id']
                target_state = target_health['TargetHealth']['State']
                as_instance_status[tg_arn][target_id] = "healthy" if target_state.lower() == "healthy" else "unhealthy"
        return as_instance_status
