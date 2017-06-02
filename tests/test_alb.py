from mock import MagicMock, mock

from libs.alb import deregister_instance_from_alb, register_instance_from_alb
from tests.helpers import LOG_FILE, mocked_logger, get_aws_data


@mock.patch('libs.alb.log', new=mocked_logger)
def test_copy_alb():
    pass


@mock.patch('libs.alb.log', new=mocked_logger)
def test_deregister_instance_from_elb():
    connection = MagicMock()

    connection.deregister_targets.return_value = ['id0', 'id1']

    ret = deregister_instance_from_alb(connection, ['test-alb'], ['id0', 'id1'], LOG_FILE)

    assert ret == True
    connection.deregister_targets.assert_called_once_with(TargetGroupArn='test-alb', Targets=['id0', 'id1'])


@mock.patch('libs.alb.log', new=mocked_logger)
def test_register_instance_from_elb():
    connection = MagicMock()

    connection.register_targets.return_value = ['id0', 'id1']

    register_instance_from_alb(connection, ['test-alb'], ['id0', 'id1'], LOG_FILE)

    connection.register_targets.assert_called_once_with(TargetGroupArn='test-alb', Targets=['id0', 'id1'])
