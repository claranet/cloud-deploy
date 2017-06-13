from mock import MagicMock, mock

from libs.elb import copy_elb
from libs.elb import deregister_instance_from_elb, deregister_all_instances_from_elb
from libs.elb import register_instance_from_elb, register_all_instances_to_elb
from tests.helpers import LOG_FILE, mocked_logger, get_aws_data


@mock.patch('libs.elb.log', new=mocked_logger)
def test_copy_elb():
    connection = MagicMock()

    def describe_load_balancers(LoadBalancerNames=None):
        if LoadBalancerNames == ['test-elb']:
            return get_aws_data('elb--describe-load-balancers')
        if LoadBalancerNames == ['copied_elb']:
            return None
        raise Exception('describe_load_balancers : Invalid parameter LoadBalancerNames')
    connection.describe_load_balancers.side_effect = describe_load_balancers

    connection.describe_tags.return_value = get_aws_data('elb--describe-tags')
    connection.describe_load_balancer_attributes.return_value = get_aws_data('elb--describe-load-balancers-attributes')
    connection.create_load_balancer.return_value.__getitem__.side_effect = {"DNSName": "test-dns"}.__getitem__

    dns = copy_elb(connection, 'copied_elb', 'test-elb', {'Key': 'foo', 'Value': 'bar'}, LOG_FILE)

    assert dns == "test-dns"

    assert connection.describe_load_balancers.call_count == 2

    connection.describe_tags.assert_called_once_with(LoadBalancerNames=['test-elb'])
    connection.describe_load_balancer_attributes.assert_called_once_with(LoadBalancerName='test-elb')

    connection.create_load_balancer.assert_called_once_with(
        LoadBalancerName='copied_elb',
        Listeners=[{
            "LoadBalancerPort": 80,
            "Protocol": "HTTP",
            "InstancePort": 80,
            "InstanceProtocol": "HTTP"
        }],
        Subnets=["subnet-test"],
        SecurityGroups=["sg-test"],
        Scheme="internet-facing",
        Tags=[
            {"Key": "test-key", "Value": "test-value"},
            {"Key": "foo", "Value": "bar"},
        ])

    connection.configure_health_check.assert_called_once_with(
        LoadBalancerName='copied_elb',
        HealthCheck={"Interval": 20, "Timeout": 6, "Target": "TCP:80", "UnhealthyThreshold": 4, "HealthyThreshold": 2}
    )

    connection.modify_load_balancer_attributes.assert_called_once_with(
        LoadBalancerName='copied_elb',
        LoadBalancerAttributes={
            "AccessLog": {"Enabled": False},
            "CrossZoneLoadBalancing": {"Enabled": True},
            "ConnectionDraining": {"Enabled": True, "Timeout": 400},
            "ConnectionSettings": {"IdleTimeout": 400}
        }
    )


@mock.patch('libs.elb.log', new=mocked_logger)
def test_deregister_instance_from_elb():
    connection = MagicMock()

    ret = deregister_instance_from_elb(connection, ['test-elb'], ['id0', 'id1'], LOG_FILE)

    assert ret == True
    connection.deregister_instances.assert_called_once_with('test-elb', ['id0', 'id1'])


@mock.patch('libs.elb.log', new=mocked_logger)
def test_deregister_all_instances_from_elb():
    connection = MagicMock()

    ret = deregister_all_instances_from_elb(connection, {'test-elb': {'id0':'inservice', 'id1': 'inservice'}}, LOG_FILE)

    assert ret == True
    connection.deregister_instances.assert_called_once_with('test-elb', ['id0', 'id1'])


@mock.patch('libs.elb.log', new=mocked_logger)
def test_register_instance_from_elb():
    connection = MagicMock()

    register_instance_from_elb(connection, ['test-elb'], ['id0', 'id1'], LOG_FILE)

    connection.register_instances.assert_called_once_with('test-elb', ['id0', 'id1'])


@mock.patch('libs.elb.log', new=mocked_logger)
def test_register_all_instances_to_elb():
    connection = MagicMock()

    register_all_instances_to_elb(connection, ['test-elb'], {'test-elb2': {'id0':'inservice', 'id1': 'inservice'}}, LOG_FILE)

    connection.register_instances.assert_called_once_with('test-elb', ['id0', 'id1'])