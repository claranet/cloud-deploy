from mock import MagicMock, mock

from libs.load_balancing import AwsMixedLoadBalancersManager
from tests.helpers import LOG_FILE, mocked_logger, get_aws_data


@mock.patch('libs.load_balancing.log', new=mocked_logger)
def test_get_instances_status_from_autoscale():
    cloud_connection = MagicMock()
    connection = MagicMock()
    cloud_connection.get_connection.return_value = connection

    connection.describe_load_balancers.return_value = get_aws_data('elbv2--describe-load-balancers')
    connection.describe_target_groups.return_value = get_aws_data('elbv2--describe-target-groups')
    connection.describe_load_balancer_target_groups.return_value = get_aws_data('autoscaling--describe-load-balancer-target-groups')

    ret = AwsMixedLoadBalancersManager(cloud_connection, 'region').get_instances_status_from_autoscale('as_test', LOG_FILE)

    assert ret == {}
    connection.describe_load_balancer_target_groups.assert_called_once_with(AutoScalingGroupName='as_test')
    assert connection.describe_target_groups.call_count == 0
    assert connection.describe_load_balancers.call_count == 0
