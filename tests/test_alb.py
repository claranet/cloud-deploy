from mock import MagicMock, mock

from libs.load_balancing import AwsAlbManager
from tests.helpers import LOG_FILE, mocked_logger, get_aws_data


@mock.patch('libs.load_balancing.log', new=mocked_logger)
def test_copy_alb():
    pass


@mock.patch('libs.load_balancing.log', new=mocked_logger)
def test_deregister_instance_from_elb():
    cloud_connection = MagicMock()
    connection = MagicMock()
    cloud_connection.get_connection.return_value = connection

    connection.describe_load_balancers.return_value = get_aws_data('elbv2--describe-load-balancers')
    connection.describe_target_groups.return_value = get_aws_data('elbv2--describe-target-groups')
    connection.deregister_targets.return_value = ['id0', 'id1']

    ret = AwsAlbManager(cloud_connection, 'region').deregister_instance_from_elb(['test-alb'], ['id0', 'id1'], LOG_FILE)

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
    connection.register_targets.return_value = ['id0', 'id1']

    AwsAlbManager(cloud_connection, 'region').register_instance_from_elb(['test-alb'], ['id0', 'id1'], LOG_FILE)

    connection.register_targets.assert_called_once_with(
        TargetGroupArn='arn:aws:elasticloadbalancing:eu-central-1:0123456789:targetgroup/tg-test/0123456789',
        Targets=[{'Id': 'id0'}, {'Id': 'id1'}]
    )
