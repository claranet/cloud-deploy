from mock import mock, MagicMock, call

from commands.preparebluegreen import Preparebluegreen
from commands.purgebluegreen import Purgebluegreen
from commands.swapbluegreen import Swapbluegreen
from tests.helpers import get_test_application, mocked_logger, LOG_FILE


@mock.patch('commands.preparebluegreen.load_balancing')
@mock.patch('commands.preparebluegreen.update_auto_scale')
@mock.patch('commands.preparebluegreen.resume_autoscaling_group_processes')
@mock.patch('commands.preparebluegreen.suspend_autoscaling_group_processes')
@mock.patch('commands.preparebluegreen.get_autoscaling_group_and_processes_to_suspend')
@mock.patch('commands.preparebluegreen.cloud_connections')
@mock.patch('commands.preparebluegreen.get_blue_green_apps')
@mock.patch('commands.preparebluegreen.check_app_manifest', new=lambda a, b, c: True)
@mock.patch('commands.preparebluegreen.check_autoscale_exists', new=lambda a, b, c: True)
@mock.patch('commands.preparebluegreen.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('ghost_aws.log', new=mocked_logger)
def test_prepare_bluegreen(get_blue_green_apps,
                           cloud_connections,
                           get_autoscaling_group_and_processes_to_suspend,
                           suspend_autoscaling_group_processes,
                           resume_autoscaling_group_processes,
                           update_auto_scale,
                           load_balancing):
    # Set up mocks and variables
    green_app = get_test_application(name="test-app-green", _id='id_green', autoscale={'name': 'autoscale-green'})
    blue_app = get_test_application(name="test-app-blue", _id='id_blue', autoscale={'name': 'autoscale-blue'})

    connection_mock = MagicMock()
    connection_pool = MagicMock()
    cloud_connections.get.return_value.return_value = connection_pool
    connection_pool.get_connection.return_value = connection_mock

    worker = MagicMock()
    worker.app = green_app
    worker.log_file = LOG_FILE

    def assert_done(status, message=None):
        assert status == "done", "Status is {} and not done : {}".format(status, message)
    worker.update_status = assert_done

    # blue app is online and green app is offline
    get_blue_green_apps.return_value = (
        blue_app,
        green_app
    )

    load_balancing.get_lb_manager.return_value.list_from_autoscale.return_value = ['elb_online']

    def get_asgapts_behavior(as_conn, app, log_file):
        if app == green_app:
            return 'autoscale-green', ['suspend_process']
        if app == blue_app:
            return 'autoscale-blue', []
        raise Exception("get_autoscaling_group_and_processes_to_suspend : application in parameter is not correct")
    get_autoscaling_group_and_processes_to_suspend.side_effect = get_asgapts_behavior

    # Launching command
    swap_cmd = Preparebluegreen(worker)
    swap_cmd.execute()

    # Check that everything has gone as planned
    load_balancing.get_lb_manager.assert_called_once_with(
        connection_pool, "eu-west-1", 'elb')

    assert get_blue_green_apps.called == 1

    suspend_autoscaling_group_processes.assert_called_once_with(
        connection_mock, 'autoscale-green', ['suspend_process'], LOG_FILE)
    resume_autoscaling_group_processes.assert_called_once_with(
        connection_mock, 'autoscale-green', ['suspend_process'], LOG_FILE)

    update_auto_scale.assert_called_once_with(connection_pool, green_app, None, LOG_FILE, update_as_params=True)

    load_balancing.get_lb_manager.return_value.copy.assert_called_once_with(
        'bgtmp-id_green', 'elb_online', {'bluegreen-temporary': 'true', 'app_id': 'id_green'}, LOG_FILE)

    load_balancing.get_lb_manager.return_value.register_into_autoscale.assert_called_once_with(
        'autoscale-green', [], ['bgtmp-id_green'], LOG_FILE)


@mock.patch('commands.swapbluegreen.load_balancing')
@mock.patch('commands.swapbluegreen.resume_autoscaling_group_processes')
@mock.patch('commands.swapbluegreen.suspend_autoscaling_group_processes')
@mock.patch('commands.swapbluegreen.get_autoscaling_group_and_processes_to_suspend')
@mock.patch('commands.swapbluegreen.cloud_connections')
@mock.patch('commands.swapbluegreen.get_blue_green_apps')
@mock.patch('commands.swapbluegreen.check_app_manifest', new=lambda a, b, c: True)
@mock.patch('commands.swapbluegreen.check_autoscale_exists', new=lambda a, b, c: True)
@mock.patch('commands.swapbluegreen.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('ghost_aws.log', new=mocked_logger)
def test_swap_bluegreen_clb(get_blue_green_apps,
                            cloud_connections,
                            get_autoscaling_group_and_processes_to_suspend,
                            suspend_autoscaling_group_processes,
                            resume_autoscaling_group_processes,
                            load_balancing):
    # Set up mocks and variables
    green_app = get_test_application(name="test-app-green", _id='id_green', autoscale={'name': 'autoscale-green'})
    blue_app = get_test_application(name="test-app-blue", _id='id_blue', autoscale={'name': 'autoscale-blue'})

    connection_mock = MagicMock()
    connection_pool = MagicMock()
    cloud_connections.get.return_value.return_value = connection_pool
    connection_pool.get_connection.return_value = connection_mock

    worker = MagicMock()
    worker.app = green_app
    worker.log_file = LOG_FILE

    load_balancing.LB_TYPE_AWS_CLB = 'aws_clb'

    def assert_done(status, message=None):
        assert status == "done", "Status is {} and not done : {}".format(status, message)
    worker.update_status = assert_done

    # blue app is online and green app is offline
    get_blue_green_apps.return_value = (
        blue_app,
        green_app
    )

    def get_isag_behavior(as_group, log_file):
        if as_group == 'autoscale-green':
            return {'elb_temp': {'instance_green1': 'inservice'}}
        if as_group == 'autoscale-blue':
            return {'elb_online': {'instance_blue1': 'inservice'}}
        raise Exception("get_elb_instance_status_autoscaling_group : auto scale parameter is not correct")
    load_balancing.get_lb_manager.return_value.get_instance_status_autoscaling_group.side_effect = get_isag_behavior

    def get_asgapts_behavior(as_conn, app, log_file):
        if app == green_app:
            return 'autoscale-green', ['suspend_process']
        if app == blue_app:
            return 'autoscale-blue', []
        raise Exception("get_autoscaling_group_and_processes_to_suspend : application in parameter is not correct")
    get_autoscaling_group_and_processes_to_suspend.side_effect = get_asgapts_behavior

    # Launching command
    swap_cmd = Swapbluegreen(worker)
    swap_cmd.execute()

    # Check that everything has gone as planned
    load_balancing.get_lb_manager.assert_called_once_with(
        connection_pool, "eu-west-1", 'elb')

    assert get_blue_green_apps.called == 1

    assert suspend_autoscaling_group_processes.call_count == 2
    suspend_autoscaling_group_processes.assert_has_calls([
        call(connection_mock, 'autoscale-green', ['suspend_process'], LOG_FILE),
        call(connection_mock, 'autoscale-blue', [], LOG_FILE)
    ], True)

    assert resume_autoscaling_group_processes.call_count == 2
    resume_autoscaling_group_processes.assert_has_calls([
        call(connection_mock, 'autoscale-green', ['suspend_process'], LOG_FILE),
        call(connection_mock, 'autoscale-blue', [], LOG_FILE)
    ], True)

    assert load_balancing.get_lb_manager.return_value.register_all_instances_to_elb.call_count == 2
    load_balancing.get_lb_manager.return_value.register_all_instances_to_elb.assert_has_calls([
        call(['elb_online'], {'elb_temp': {'instance_green1': 'inservice'}}, LOG_FILE),
        call(['elb_temp'],  {'elb_online': {'instance_blue1': 'inservice'}}, LOG_FILE)
    ], False)

    assert load_balancing.get_lb_manager.return_value.deregister_all_instances_from_elb.call_count == 2
    load_balancing.get_lb_manager.return_value.deregister_all_instances_from_elb.assert_has_calls([
        call({'elb_online': {'instance_blue1': 'inservice'}}, LOG_FILE),
        call({'elb_temp': {'instance_green1': 'inservice'}}, LOG_FILE)
    ], False)


@mock.patch('commands.purgebluegreen.load_balancing')
@mock.patch('commands.purgebluegreen.flush_instances_update_autoscale')
@mock.patch('commands.purgebluegreen.suspend_autoscaling_group_processes')
@mock.patch('commands.purgebluegreen.get_autoscaling_group_and_processes_to_suspend')
@mock.patch('commands.purgebluegreen.get_blue_green_destroy_temporary_elb_config', new=lambda a: True)
@mock.patch('commands.purgebluegreen.cloud_connections')
@mock.patch('commands.purgebluegreen.get_blue_green_apps')
@mock.patch('commands.purgebluegreen.check_autoscale_exists', new=lambda a, b, c: True)
@mock.patch('commands.purgebluegreen.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('ghost_aws.log', new=mocked_logger)
def test_purge_bluegreen(get_blue_green_apps,
                         cloud_connections,
                         get_autoscaling_group_and_processes_to_suspend,
                         suspend_autoscaling_group_processes,
                         flush_instances_update_autoscale,
                         load_balancing):
    # Set up mocks and variables
    green_app = get_test_application(name="test-app-green", _id='id_green', autoscale={'name': 'autoscale-green'})
    blue_app = get_test_application(name="test-app-blue", _id='id_blue', autoscale={'name': 'autoscale-blue'})

    connection_mock = MagicMock()
    connection_pool = MagicMock()
    cloud_connections.get.return_value.return_value = connection_pool
    connection_pool.get_connection.return_value = connection_mock

    worker = MagicMock()
    worker.app = green_app
    worker.log_file = LOG_FILE

    def assert_done(status, message=None):
        assert status == "done", "Status is {} and not done : {}".format(status, message)
    worker.update_status = assert_done

    # blue app is online and green app is offline
    get_blue_green_apps.return_value = (
        blue_app,
        green_app
    )

    load_balancing.get_lb_manager.return_value.list_from_autoscale.return_value = ['bgtmp-id_green']

    get_autoscaling_group_and_processes_to_suspend.return_value = ('autoscale-green', ['suspend_process'])

    # Launching command
    swap_cmd = Purgebluegreen(worker)
    swap_cmd.execute()

    # Check that everything has gone as planned
    assert get_blue_green_apps.called == 1

    get_autoscaling_group_and_processes_to_suspend.assert_called_once_with(
        connection_mock, green_app, LOG_FILE)

    suspend_autoscaling_group_processes.assert_called_once_with(
        connection_mock, 'autoscale-green', ['suspend_process'], LOG_FILE)

    flush_instances_update_autoscale.assert_called_once_with(
        connection_mock, connection_pool, green_app, LOG_FILE)

    load_balancing.get_lb_manager.return_value.register_into_autoscale.assert_called_once_with(
        'autoscale-green', ['bgtmp-id_green'], None, LOG_FILE)

    load_balancing.get_lb_manager.return_value.destroy.assert_called_once_with(
        'bgtmp-id_green', LOG_FILE)
