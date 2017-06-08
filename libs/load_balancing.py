import itertools
from botocore.exceptions import ClientError

import ghost_aws
from ghost_log import log
from libs.autoscaling import get_autoscaling_group_object

LB_TYPE_AWS_CLB   = 'elb'
LB_TYPE_AWS_ALB   = 'alb'
LB_TYPE_AWS_MIXED = 'aws_mixed'


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
    if lb_type == LB_TYPE_AWS_MIXED:
        return AwsMixedLoadBalancersManager(cloud_connection, region)
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
        if item.lower() == 'dns_name':
            value = self._data.get('DNSName', value)
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

    def get_health_check(self, lb_name):
        """
            returns the health check configuration as dict like {'interval': '',
                      'timeout': '', 'unhealthy_threshold': '', 'healthy_threshold': '',
                      'protocol': '', 'port': '', 'path': '', 'target': ''}
            :param lb_name: string: resource name
            :returns dict:
        """
        raise NotImplementedError()

    def configure_health_check(self, lb_name, interval=None, timeout=None, unhealthy_threshold=None,
                               healthy_threshold=None, protocol=None, port=None, path=None, target=None):
        """
            Configures the HealthCheck value
            :param lb_name: string: resource name
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

    def get_by_name(self, lb_name):
        """
            :return the found LB object
        """
        raise NotImplementedError()

    def get_dns_name(self, lb_name):
        """ Return the DNS name for the passed LB

            :param  lb_name:  string: The name of the Elastic Load Balancer.
            :return string
        """
        raise NotImplementedError()

    def list_from_autoscale(self, as_name, log_file, filter_tag=None):
        """ Return a list of LB names defined in
            the Autoscaling Group in parameter.

            :param log_file:
            :param  as_name:  string: The Autoscaling Group name.
            :param  filter_tag: dict: A dict with a unique value that will be used as a filter for tags
            :return  a list of LB names.
        """
        raise NotImplementedError()

    def copy_lb(self, new_lb_name, source_lb_name, additional_tags, log_file):
        """ Copy an existing LB, currently copies basic configuration
            (Subnets, SGs, first listener), health check and tags.

            :param new_lb_name: string: created LB name
            :param source_lb_name: string: source LB name
            :param additional_tags: dict: tags to add to the new lb
            :param log_file: string: log file
            :return created LB endpoint
        """
        raise NotImplementedError()

    def destroy_lb(self, lb_name, log_file):
        """ Destroy the specified LB

            :param  lb_name:  string: The name of the Load Balancer.
            :param  log_file: string: log file
        """
        raise NotImplementedError()

    def register_into_autoscale(self, as_name, lb_names_to_deregister, lb_names_to_register, log_file):
        """ Modify the AutoScale Group to set the list of LB to use

        :param  as_name:  string: string of the autoscaling group name.
        :param  lb_names_to_deregister:  list: The name of the Elastic Load Balancers.
        :param  lb_names_to_register:  list: The name of the Elastic Load Balancers.
        :param  log_file: string: The log file
        :return boolean(True if succeed otherwise False)
        """
        raise NotImplementedError()

    def get_instances_status_from_autoscale(self, as_name, log_file):
        """ Return a dict of instance ids as key and their status as value per LB.

            :param log_file:
            :param  as_name: string of the autoscaling group name.
            :return dict(ex: {'lb_XXX1':{'instance_id':'inservice/outofservice'}})
        """
        raise NotImplementedError()

    def get_instances_status_fom_lb(self, lb_names):
        """ Return a dict of instance ids as key and their status as value per LB.

            :param  lb_names: list: The name of the Elastic Load Balancers.
            :return dict(ex: {'lb_XXX1':{'instance_id':'inservice/outofservice'}})
        """
        raise NotImplementedError()

    def deregister_instances_from_lbs(self, lb_names, instances_ids, log_file):
        """ Registrer one or multiple instances in the LB pool.

            :param  lb_names: list The name of the Elastic Load Balancers.
            :param  instances_ids: list of instances ID to add to the LB pool.
            :param  log_file:  string  The log file
            :return boolean(True if succeed otherwise False)
        """
        raise NotImplementedError()

    # TODO refactor code to remove this function
    def deregister_all_instances_from_lbs(self, lbs_with_instances, log_file):
        """ DEPRECATED : Deregistrer one or multiple instances in the LB pool.

            :param  lbs_with_instances: list The name of the Elastic Load Balancers, and all instances in one of them.
                    (dict(ex: {'lb_XXX1':{'instance_id':'inservice/outofservice'}}))
            :param  log_file:  string  The log file
            :return boolean(True if succeed otherwise False)
        """
        raise NotImplementedError()

    def register_instances_from_lbs(self, lb_names, instances_ids, log_file):
        """ Registrer one or multiple instances in the LB pool.

            :param  lb_names: list The name of the Elastic Load Balancers.
            :param  instances_ids: list of instances ID to add to the LB pool.
            :param  log_file:  string  The log file
            :return boolean(True if succeed otherwise False)
        """
        raise NotImplementedError()

    # TODO refactor code to remove this function
    def register_all_instances_to_lbs(self, lb_names, instances, log_file):
        """ DEPRECATED : Registrer one or multiple instances in the LB pool.

            :param  lb_names: list The name of the Elastic Load Balancers.
            :param  instances: list The name of the Elastic Load Balancers, and all instances in one of them.
                    (dict(ex: {'lb_XXX1':{'instance_id':'inservice/outofservice'}}))
            :param  log_file:  string  The log file
            :return boolean(True if succeed otherwise False)
        """
        raise NotImplementedError()

    def get_connection_draining_value(self, lb_names):
        """ Return the biggest connection draining value for the list of LB in parameters.

            :param  lb_names: list The name of the Elastic Load Balancers.
            :return  int  The value in seconds of the connection draining.
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

    def get_by_name(self, lb_name):
        elb_conn = self._get_elb_connection()
        try:
            elb = elb_conn.describe_load_balancers(
                LoadBalancerNames=[lb_name])['LoadBalancerDescriptions'][0]
            return LoadBalancerItem(elb)
        except Exception:
            return None

    def get_dns_name(self, lb_name):
        return self.get_by_name(lb_name).dns_name

    def register_instances_from_lbs(self, lb_names, instances_ids, log_file):
        try:
            elb_conn = self._get_elb_connection()
            for elb_name in lb_names:
                if not elb_conn.register_instances(elb_name, instances_ids).status:
                    log("Failed to register instances {0} in the ELB {1}".format(str(instances_ids), elb_name),
                        log_file)
                    raise Exception()
                else:
                    log("Instances {0} well registered in the ELB {1}".format(str(instances_ids), elb_name), log_file)
            return True
        except Exception as e:
            log("Exception during register operation: {0}".format(str(e)), log_file)
            raise

    def deregister_instances_from_lbs(self, lb_names, instances_ids, log_file):
        try:
            elb_conn2 = self._get_elb_connection(boto2_compat=True)
            for elb_name in lb_names:
                if not elb_conn2.deregister_instances(elb_name, instances_ids).status:
                    log("Failed to deregister instances {0} in the ELB {1}".format(str(instances_ids), elb_name),
                        log_file)
                    raise Exception()
                else:
                    log("Instances {0} well deregistered in the ELB {1}" .format(str(instances_ids), elb_name),
                        log_file)
            return True
        except Exception as e:
            log("Exception during deregister operation: {0}" .format(str(e)), log_file)
            raise

    def deregister_all_instances_from_lbs(self, lbs_with_instances, log_file):
        try:
            elb_conn2 = self._get_elb_connection(boto2_compat=True)
            for elb_name, elb_instances in lbs_with_instances.items():
                # sorted is only used in order to have predictable method calls for test cases
                instance_names = sorted(elb_instances.keys())
                if not elb_conn2.deregister_instances(elb_name, instance_names).status:
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

    def register_all_instances_to_lbs(self, lb_names, instances, log_file):
        try:
            elb_conn2 = self._get_elb_connection(boto2_compat=True)
            for elb_name in lb_names:
                for unused_elb_name, elb_instances in instances.items():
                    # sorted is only used in order to have predictable method calls for test cases
                    instance_names = sorted(elb_instances.keys())
                    if not elb_conn2.register_instances(elb_name, instance_names).status:
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

    def get_instances_status_fom_lb(self, lb_names):
        elb_conn2 = self._get_elb_connection(boto2_compat=True)
        as_instance_status = {}
        for elb in lb_names:
            as_instance_status[elb] = {}
            for instance in elb_conn2.describe_instance_health(elb):
                as_instance_status[elb][
                    instance.instance_id] = "inservice" if instance.state.lower() == "inservice" else "outofservice"
        return as_instance_status

    def register_into_autoscale(self, as_name, lb_names_to_deregister, lb_names_to_register, log_file):
        as_conn = self._get_as_connection()
        try:
            if lb_names_to_deregister and len(lb_names_to_deregister) > 0:
                as_conn.detach_load_balancers(AutoScalingGroupName=as_name, LoadBalancerNames=lb_names_to_deregister)
            if lb_names_to_register and len(lb_names_to_register) > 0:
                as_conn.attach_load_balancers(AutoScalingGroupName=as_name, LoadBalancerNames=lb_names_to_register)
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

    def get_instances_status_from_autoscale(self, as_name, log_file):
        elb_conn2 = self._get_elb_connection(boto2_compat=True)
        as_instance_status = {}
        for elb in self.list_from_autoscale(as_name, log_file):
            as_instance_status[elb] = {}
            for instance in elb_conn2.describe_instance_health(elb):
                as_instance_status[elb][
                    instance.instance_id] = "inservice" if instance.state.lower() == "inservice" else "outofservice"
        return as_instance_status

    def copy_lb(self, new_lb_name, source_lb_name, additional_tags, log_file):
        elb_conn = self._get_elb_connection()
        dest_elb = self.get_by_name(new_lb_name)
        if dest_elb:
            log("  INFO: ELB {0} already available, no copy needed".format(new_lb_name), log_file)
            return dest_elb['DNSName']
        source_elb = self.get_by_name(source_lb_name)
        source_elb_listener = source_elb['ListenerDescriptions'][0]['Listener']
        source_elb_tags = elb_conn.describe_tags(
            LoadBalancerNames=[source_lb_name]
        )['TagDescriptions'][0]['Tags']
        source_elb_attributes = elb_conn.describe_load_balancer_attributes(
            LoadBalancerName=source_lb_name
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
        response = elb_conn.create_load_balancer(
            LoadBalancerName=new_lb_name,
            Listeners=[dest_elb_listener],
            Subnets=source_elb['Subnets'],
            SecurityGroups=source_elb['SecurityGroups'],
            Scheme=source_elb['Scheme'],
            Tags=source_elb_tags + ghost_aws.dict_to_aws_tags(additional_tags)
        )

        # Configure Healthcheck
        elb_conn.configure_health_check(
            LoadBalancerName=new_lb_name,
            HealthCheck=source_elb['HealthCheck']
        )

        # Update ELB attributes
        elb_conn.modify_load_balancer_attributes(
            LoadBalancerName=new_lb_name,
            LoadBalancerAttributes=source_elb_attributes
        )

        return response['DNSName']

    def destroy_lb(self, lb_name, log_file):
        elb_conn = self._get_elb_connection()
        log("  INFO: Destroying ELB {0}".format(lb_name), log_file)
        elb_conn.delete_load_balancer(LoadBalancerName=lb_name)

    def get_connection_draining_value(self, lb_names):
        elb_conn2 = self._get_elb_connection(boto2_compat=True)
        return max([elb_conn2.get_all_lb_attributes(elb).connection_draining.timeout for elb in lb_names])

    def get_health_check(self, lb_name):
        elb = self.get_by_name(lb_name)
        return {k: elb['HealthCheck'].get(v) for k, v in self.HEALTHCHECK_PARAMS_MAPPING.items()}

    def configure_health_check(self, lb_name, interval=None, timeout=None, unhealthy_threshold=None,
                               healthy_threshold=None, protocol=None, port=None, path=None, target=None):
        elb_conn = self._get_elb_connection()
        cur_health_check = self.get_by_name(lb_name)['HealthCheck']

        func_params = locals()
        cur_health_check.update({v: func_params[p]
                                 for p, v in self.HEALTHCHECK_PARAMS_MAPPING.items() if func_params.get(p, None)})
        elb_conn.configure_health_check(
            LoadBalancerName=lb_name,
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
        lbtg = conn.describe_load_balancer_target_groups(AutoScalingGroupName=as_name)['LoadBalancerTargetGroups']
        return [tg['LoadBalancerTargetGroupARN'] for tg in lbtg if tg['State'] not in ('Removing', 'Removed')]

    def _get_targetgroup_arns_from_alb(self, alb_arn):
        return [tg['TargetGroupArn']
                for tg in self._get_alb_connection().describe_target_groups(LoadBalancerArn=alb_arn)['TargetGroups']]

    def get_by_name(self, lb_name):
        alb_conn = self._get_alb_connection()
        try:
            alb = alb_conn.describe_load_balancers(
                Names=[lb_name]
            )['LoadBalancers'][0]
            return LoadBalancerItem(alb)
        except Exception as e:
            if e.__class__.__name__ == 'LoadBalancerNotFoundException':
                return None
            raise

    def get_dns_name(self, lb_name):
        return self.get_by_name(lb_name).dns_name

    def get_connection_draining_value(self, lb_names):
        alb_conn = self._get_alb_connection()
        values = []
        alb_arns = ([alb['LoadBalancerArn']
                     for alb in alb_conn.describe_load_balancers(Names=lb_names)['LoadBalancers']])
        for alb_arn in alb_arns:
            for tg_arn in self._get_targetgroup_arns_from_alb(alb_arn):
                attrs = alb_conn.describe_target_group_attributes(TargetGroupArn=tg_arn)['Attributes']
                for at in attrs:
                    if at['Key'] == 'deregistration_delay.timeout_seconds':
                        values.append(int(at['Value']))
                        break
        return max(values)

    def copy_lb(self, new_lb_name, source_lb_name, additional_tags, log_file):
        alb_conn = self._get_alb_connection()
        dest_alb = self.get_by_name(new_lb_name)
        if dest_alb:
            log("  INFO: ALB {0} already available, no copy needed".format(new_lb_name), log_file)
            return dest_alb['DNSName']
        source_alb = self.get_by_name(source_lb_name)
        source_alb_arn = source_alb['LoadBalancerArn']

        source_alb_tags = alb_conn.describe_tags(
            ResourceArns=[source_alb_arn]
        )['TagDescriptions'][0]['Tags']

        source_alb_attributes = alb_conn.describe_load_balancer_attributes(
            LoadBalancerArn=source_alb_arn
        )['Attributes']

        # Create ALB
        dest_alb = alb_conn.create_load_balancer(
            Name=new_lb_name,
            Subnets=[az['SubnetId'] for az in source_alb['AvailabilityZones']],
            SecurityGroups=source_alb['SecurityGroups'],
            Scheme=source_alb['Scheme'],
            Tags=source_alb_tags + ghost_aws.dict_to_aws_tags(additional_tags)
        )['LoadBalancers'][0]
        dest_alb_arn = dest_alb['LoadBalancerArn']

        # Update ALB attributes
        alb_conn.modify_load_balancer_attributes(
            LoadBalancerArn=dest_alb_arn,
            Attributes=[attr for attr in source_alb_attributes if attr['Value'] != '']
        )

        # Copy target group
        source_tg_list = alb_conn.describe_target_groups(LoadBalancerArn=source_alb_arn)['TargetGroups']
        if len(source_tg_list) > 1:
            raise LoadBalancerManagerException('Multiple target groups for an ALB is currently not supported')
        source_tg = source_tg_list[0]
        source_tg_arn = source_tg['TargetGroupArn']
        source_tg_attributes = alb_conn.describe_target_group_attributes(TargetGroupArn=source_tg_arn)['Attributes']

        response = alb_conn.create_target_group(
            Name='tg-{}'.format(new_lb_name)[:31],
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
        alb_conn.add_tags(ResourceArns=[dest_tg_arn],
                          Tags=ghost_aws.dict_to_aws_tags(additional_tags))
        alb_conn.modify_target_group_attributes(
            TargetGroupArn=dest_tg_arn,
            Attributes=[attr for attr in source_tg_attributes if attr['Value'] != '']
        )

        # Creating listeners
        source_listeners = alb_conn.describe_listeners(LoadBalancerArn=source_alb_arn)
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
            alb_conn.create_listener(**params)

        return dest_alb['DNSName']

    def destroy_lb(self, lb_name, log_file):
        alb_conn = self._get_alb_connection()

        alb = alb_conn.describe_load_balancers(Names=[lb_name])['LoadBalancers'][0]
        alb_arn = alb['LoadBalancerArn']
        listeners_arns = [tg['ListenerArn']
                          for tg in alb_conn.describe_listeners(LoadBalancerArn=alb_arn)['Listeners']]
        tg_arns = [tg['TargetGroupArn']
                   for tg in alb_conn.describe_target_groups(LoadBalancerArn=alb_arn)['TargetGroups']]

        for arn in listeners_arns:
            log('Deleting LB Listener {}'.format(arn), log_file)
            alb_conn.delete_listener(ListenerArn=arn)
        for arn in tg_arns:
            log('Deleting Target Group {}'.format(arn), log_file)
            alb_conn.delete_target_group(TargetGroupArn=arn)
        log('Deleting ALB {}'.format(alb_arn), log_file)
        alb_conn.delete_load_balancer(LoadBalancerArn=alb_arn)

    def _get_instance_status_from_tg(self, tg_arn):
        alb_conn = self._get_alb_connection()
        ret = {}
        for target_health in alb_conn.describe_target_health(TargetGroupArn=tg_arn)['TargetHealthDescriptions']:
            # Accepting draining state in order to behave like CLB
            state = target_health['TargetHealth']['State'].lower()
            if state != "draining":  # We do not consider draining instances as still registered
                ret[target_health['Target']['Id']] = "inservice" if state == "healthy" else "outofservice"
        return ret

    def get_instances_status_fom_lb(self, lb_names):
        alb_conn = self._get_alb_connection()
        albs = ({alb['LoadBalancerName']: alb['LoadBalancerArn']
                 for alb in alb_conn.describe_load_balancers(Names=lb_names)['LoadBalancers']})
        as_instance_status = {}
        for alb_name, alb_arn in albs.items():
            for tg_arn in self._get_targetgroup_arns_from_alb(alb_arn):
                as_instance_status[alb_name] = self._get_instance_status_from_tg(tg_arn)
        return as_instance_status

    def get_instances_status_from_autoscale(self, as_name, log_file):
        alb_conn = self._get_alb_connection()
        as_instance_status = {}
        tg_list = alb_conn.describe_target_groups(
            TargetGroupArns=self._get_targetgroup_arns_from_autoscale(as_name))['TargetGroups']
        lb_arns = list(itertools.chain(*(tg['LoadBalancerArns'] for tg in tg_list)))
        lb_names = {lb['LoadBalancerArn']: lb['LoadBalancerName']
                    for lb in alb_conn.describe_load_balancers(LoadBalancerArns=lb_arns)['LoadBalancers']}
        for tg in tg_list:
            if len(tg['LoadBalancerArns']) > 1:
                raise LoadBalancerManagerException('Multiple ALBs for a target group is currently not supported')
            as_instance_status[lb_names[tg['LoadBalancerArns'][0]]] = self._get_instance_status_from_tg(tg['TargetGroupArn'])
        return as_instance_status

    def register_into_autoscale(self, as_name, lb_names_to_deregister, lb_names_to_register, log_file):
        lb_names_to_deregister = lb_names_to_deregister or []
        lb_names_to_register = lb_names_to_register or []
        as_conn = self._get_as_connection()
        try:
            for alb in lb_names_to_register:
                alb = self.get_by_name(alb)
                source_tg_list = self._get_targetgroup_arns_from_alb(alb['LoadBalancerArn'])
                if len(source_tg_list) > 1:
                    raise LoadBalancerManagerException('Multiple target groups for an ALB is currently not supported')
                log('Attaching Target Group {0} to ASG {1}'.format(source_tg_list[0], as_name), log_file)
                as_conn.attach_load_balancer_target_groups(
                    AutoScalingGroupName=as_name, TargetGroupARNs=[source_tg_list[0]])

            for alb in lb_names_to_deregister:
                alb = self.get_by_name(alb)
                source_tg_list = self._get_targetgroup_arns_from_alb(alb['LoadBalancerArn'])
                if len(source_tg_list) > 1:
                    raise LoadBalancerManagerException('Multiple target groups for an ALB is currently not supported')
                log('Detaching Target Group {0} from ASG {1}'.format(source_tg_list[0], as_name), log_file)
                as_conn.detach_load_balancer_target_groups(
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

    def get_health_check(self, lb_name):
        alb = self.get_by_name(lb_name)
        conn = self._get_alb_connection()
        tg_list = conn.describe_target_groups(LoadBalancerArn=alb['LoadBalancerArn'])['TargetGroups']
        if len(tg_list) > 1:
            raise LoadBalancerManagerException('Multiple target groups for an ALB is currently not supported')
        return {k: tg_list[0].get(v, None) for k, v in self.HEALTHCHECK_PARAMS_MAPPING.items()}

    def configure_health_check(self, lb_name, interval=None, timeout=None, unhealthy_threshold=None,
                               healthy_threshold=None, protocol=None, port=None, path=None, target=None):
        alb_conn = self._get_alb_connection()
        func_params = locals()
        params = {v: func_params[p] for p, v in self.HEALTHCHECK_PARAMS_MAPPING.items() if func_params.get(p, None)}
        for tg_arn in self._get_targetgroup_arns_from_alb(self.get_by_name(lb_name)['LoadBalancerArn']):
            params['TargetGroupArn'] = tg_arn
            response = alb_conn.modify_target_group(**params)

    def register_all_instances_to_lbs(self, lb_names, instances, log_file):
        try:
            alb_conn = self._get_alb_connection()
            albs = ({alb['LoadBalancerName']: alb['LoadBalancerArn']
                     for alb in alb_conn.describe_load_balancers(Names=lb_names)['LoadBalancers']})
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

    def deregister_all_instances_from_lbs(self, lbs_with_instances, log_file):
        try:
            alb_conn = self._get_alb_connection()
            albs = ({alb['LoadBalancerName']: alb['LoadBalancerArn']
                     for alb in alb_conn.describe_load_balancers(Names=lbs_with_instances.keys())['LoadBalancers']})
            for alb_name, alb_arn in albs.items():
                tg_list = alb_conn.describe_target_groups(LoadBalancerArn=alb_arn)['TargetGroups']
                if len(tg_list) > 1:
                    raise LoadBalancerManagerException('Multiple target groups for an ALB is currently not supported')
                tg_arn = tg_list[0]['TargetGroupArn']
                # sorted is only used in order to have predictable method calls for test cases
                instance_names = sorted(lbs_with_instances[alb_name].keys())
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

    def register_instances_from_lbs(self, lb_names, instances_ids, log_file):
        try:
            alb_conn = self._get_alb_connection()
            albs = ({alb['LoadBalancerName']: alb['LoadBalancerArn']
                     for alb in alb_conn.describe_load_balancers(Names=lb_names)['LoadBalancers']})
            for alb_name, alb_arn in albs.items():
                for alb_tg_arn in self._get_targetgroup_arns_from_alb(alb_arn):
                    alb_conn.register_targets(
                        TargetGroupArn=alb_tg_arn,
                        Targets=[{'Id': host_id} for host_id in instances_ids])
                    log("Instances {0} well registered in the ALB {1}".format(str(instances_ids), alb_name), log_file)
            return True
        except Exception as e:
            log("Exception during deregister operation: {0}".format(str(e)), log_file)
            raise

    def deregister_instances_from_lbs(self, lb_names, instances_ids, log_file):
        try:
            alb_conn = self._get_alb_connection()
            albs = ({alb['LoadBalancerName']: alb['LoadBalancerArn']
                     for alb in alb_conn.describe_load_balancers(Names=lb_names)['LoadBalancers']})
            for alb_name, alb_arn in albs.items():
                for alb_tg_arn in self._get_targetgroup_arns_from_alb(alb_arn):
                    alb_conn.deregister_targets(
                        TargetGroupArn=alb_tg_arn,
                        Targets=[{'Id': host_id} for host_id in instances_ids])
                    log("Instances {0} well deregistered in the ALB {1}".format(str(instances_ids), alb_name), log_file)
            return True
        except Exception as e:
            log("Exception during deregister operation: {0}".format(str(e)), log_file)
            raise


class AwsMixedLoadBalancersManager(LoadBalancersManager):
    def __init__(self, cloud_connection, region):
        super(AwsMixedLoadBalancersManager, self).__init__(cloud_connection, region)
        self.aws_clb_mgr = AwsClbManager(cloud_connection, region)
        self.aws_alb_mgr = AwsAlbManager(cloud_connection, region)

    def get_instances_status_from_autoscale(self, as_name, log_file):
        instances = self.aws_clb_mgr.get_instances_status_from_autoscale(as_name, log_file)
        instances.update(self.aws_alb_mgr.get_instances_status_from_autoscale(as_name, log_file))
        return instances
