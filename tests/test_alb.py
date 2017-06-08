from mock import MagicMock, mock

from libs.load_balancing import AwsAlbManager
from tests.helpers import LOG_FILE, mocked_logger, get_aws_data


@mock.patch('libs.load_balancing.log', new=mocked_logger)
def test_copy_alb():
    cloud_connection = MagicMock()
    connection = MagicMock()
    cloud_connection.get_connection.return_value = connection

    def describe_load_balancers(Names=None):
        if Names == ['test-elb']:
            return get_aws_data('elbv2--describe-load-balancers')
        if Names == ['copied_elb']:
            raise type('LoadBalancerNotFoundException', (Exception,), {})
        raise Exception('describe_load_balancers : Invalid parameter Names')
    connection.describe_load_balancers.side_effect = describe_load_balancers

    connection.describe_tags.return_value = get_aws_data('elbv2--describe-tags')
    connection.describe_load_balancer_attributes.return_value = get_aws_data('elbv2--describe-load-balancers-attributes')
    connection.describe_target_groups.return_value = get_aws_data('elbv2--describe-target-groups')
    connection.describe_listeners.return_value = get_aws_data('elbv2--describe-listeners')
    connection.create_load_balancer.return_value  = {"LoadBalancers":[{"DNSName": "test-dns",
                                                                       "LoadBalancerArn": "copied-load-balancer-arn"}]}
    connection.create_target_group.return_value = {"TargetGroups": [{'TargetGroupArn': 'new-tg-arn'}]}

    dns = AwsAlbManager(cloud_connection, 'region').copy_lb('copied_elb', 'test-elb', {'foo': 'bar'}, LOG_FILE)

    assert dns == "test-dns"

    assert connection.describe_load_balancers.call_count == 2

    connection.describe_tags.assert_called_once_with(
        ResourceArns=['arn:aws:elasticloadbalancing:eu-central-1:0123456789:loadbalancer/app/alb-test/0123456789'])
    connection.describe_load_balancer_attributes.assert_called_once_with(
        LoadBalancerArn='arn:aws:elasticloadbalancing:eu-central-1:0123456789:loadbalancer/app/alb-test/0123456789')

    connection.create_load_balancer.assert_called_once_with(
        Name='copied_elb',
        Subnets=["subnet-test-1", "subnet-test-2"],
        SecurityGroups=["sg-test"],
        Scheme="internet-facing",
        Tags=[
            {"Key": "test-key", "Value": "test-value"},
            {"Key": "foo", "Value": "bar"},
        ])

    connection.create_target_group.assert_called_once_with(
        Name='tg-copied_elb',
        Protocol='HTTP',
        Port=80,
        VpcId='vpc-test',
        HealthCheckProtocol='HTTP',
        HealthCheckPort="80",
        HealthCheckPath='/',
        HealthCheckIntervalSeconds=20,
        HealthCheckTimeoutSeconds=6,
        HealthyThresholdCount=2,
        UnhealthyThresholdCount=4,
        Matcher={"HttpCode": "200"}
    )

    connection.modify_load_balancer_attributes.assert_called_once_with(
        Attributes=[
            {"Key": "access_logs.s3.enabled", "Value": "false"},
            {"Key": "deletion_protection.enabled", "Value": "false"},
            {"Key": "idle_timeout.timeout_seconds", "Value": "123"}
        ],
        LoadBalancerArn="copied-load-balancer-arn",
    )

    connection.create_listener.assert_called_once_with(
      Protocol="HTTP",
      DefaultActions=[
        {"TargetGroupArn": "new-tg-arn", "Type": "forward"}
      ],
      LoadBalancerArn="copied-load-balancer-arn",
      Port=80
    )


@mock.patch('libs.load_balancing.log', new=mocked_logger)
def test_deregister_instance_from_elb():
    cloud_connection = MagicMock()
    connection = MagicMock()
    cloud_connection.get_connection.return_value = connection

    connection.describe_load_balancers.return_value = get_aws_data('elbv2--describe-load-balancers')
    connection.describe_target_groups.return_value = get_aws_data('elbv2--describe-target-groups')

    ret = AwsAlbManager(cloud_connection, 'region').deregister_instances_from_lbs(['alb-test'], ['id0', 'id1'], LOG_FILE)

    assert ret == True
    connection.deregister_targets.assert_called_once_with(
        TargetGroupArn='arn:aws:elasticloadbalancing:eu-central-1:0123456789:targetgroup/tg-test/0123456789',
        Targets=[{'Id': 'id0'}, {'Id': 'id1'}]
    )


@mock.patch('libs.load_balancing.log', new=mocked_logger)
def test_deregister_all_instances_from_elb():
    cloud_connection = MagicMock()
    connection = MagicMock()
    cloud_connection.get_connection.return_value = connection

    connection.describe_load_balancers.return_value = get_aws_data('elbv2--describe-load-balancers')
    connection.describe_target_groups.return_value = get_aws_data('elbv2--describe-target-groups')

    ret = AwsAlbManager(cloud_connection, 'region').deregister_all_instances_from_lbs({'alb-test': {'id0': 'inservice', 'id1': 'inservice'}}, LOG_FILE)

    assert ret == True
    connection.deregister_targets.assert_called_once_with(
        TargetGroupArn='arn:aws:elasticloadbalancing:eu-central-1:0123456789:targetgroup/tg-test/0123456789',
        Targets=[{'Id': 'id0'}, {'Id': 'id1'}]
    )


@mock.patch('libs.load_balancing.log', new=mocked_logger)
def test_register_instance_from_elb():
    cloud_connection = MagicMock()
    connection = MagicMock()
    cloud_connection.get_connection.return_value = connection

    connection.describe_load_balancers.return_value = get_aws_data('elbv2--describe-load-balancers')
    connection.describe_target_groups.return_value = get_aws_data('elbv2--describe-target-groups')

    AwsAlbManager(cloud_connection, 'region').register_instances_from_lbs(['alb-test'], ['id0', 'id1'], LOG_FILE)

    connection.register_targets.assert_called_once_with(
        TargetGroupArn='arn:aws:elasticloadbalancing:eu-central-1:0123456789:targetgroup/tg-test/0123456789',
        Targets=[{'Id': 'id0'}, {'Id': 'id1'}]
    )

@mock.patch('libs.load_balancing.log', new=mocked_logger)
def test_register_all_instances_to_elb():
    cloud_connection = MagicMock()
    connection = MagicMock()
    cloud_connection.get_connection.return_value = connection

    connection.describe_load_balancers.return_value = get_aws_data('elbv2--describe-load-balancers')
    connection.describe_target_groups.return_value = get_aws_data('elbv2--describe-target-groups')

    ret = AwsAlbManager(cloud_connection, 'region').register_all_instances_to_lbs(['alb-test'], {'alb-test2': {'id0': 'inservice', 'id1': 'inservice'}}, LOG_FILE)

    assert ret == True
    connection.register_targets.assert_called_once_with(
        TargetGroupArn='arn:aws:elasticloadbalancing:eu-central-1:0123456789:targetgroup/tg-test/0123456789',
        Targets=[{'Id': 'id0'}, {'Id': 'id1'}]
    )
