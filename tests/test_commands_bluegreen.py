from mock import mock, MagicMock, call

from commands.swapbluegreen import Swapbluegreen
from tests.helpers import get_test_application, mocked_logger


@mock.patch('commands.swapbluegreen.deregister_all_instances_from_elb')
@mock.patch('commands.swapbluegreen.register_all_instances_to_elb')
@mock.patch('commands.swapbluegreen.resume_autoscaling_group_processes')
@mock.patch('commands.swapbluegreen.suspend_autoscaling_group_processes')
@mock.patch('commands.swapbluegreen.get_elb_instance_status_autoscaling_group')
@mock.patch('commands.swapbluegreen.get_autoscaling_group_and_processes_to_suspend')
@mock.patch('commands.swapbluegreen.cloud_connections')
@mock.patch('commands.swapbluegreen.get_blue_green_apps')
@mock.patch('commands.swapbluegreen.check_app_manifest', new=lambda a, b, c: True)
@mock.patch('commands.swapbluegreen.check_autoscale_exists', new=lambda a, b, c: True)
@mock.patch('commands.swapbluegreen.log', new=mocked_logger)
@mock.patch('libs.elb.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('ghost_aws.log', new=mocked_logger)
def test_swap_bluegreen_clb(get_blue_green_apps,
                            cloud_connections,
                            get_autoscaling_group_and_processes_to_suspend,
                            get_elb_instance_status_autoscaling_group,
                            suspend_autoscaling_group_processes,
                            resume_autoscaling_group_processes,
                            register_all_instances_to_elb,
                            deregister_all_instances_from_elb):
    # Set up mocks and variables
    green_app = get_test_application(name="test-app-green", _id='id_green', autoscale={'name': 'autoscale-green'})
    blue_app = get_test_application(name="test-app-blue", _id='id_blue', autoscale={'name': 'autoscale-blue'})

    connection_mock = MagicMock()
    cloud_connections.get.return_value.return_value.get_connection.return_value = connection_mock

    worker = MagicMock()
    worker.app = green_app
    worker.log_file = 'log_file'

    def assert_done(status, message=None):
        assert status == "done", "Status is {} and not done : {}".format(status, message)
    worker.update_status = assert_done

    get_blue_green_apps.return_value = (
        blue_app,
        green_app
    )

    def get_eisag_behavior(elb_conn, as_group, conn_as):
        if as_group == 'autoscale-green':
            return {'elb_temp': {'instance_green1': 'inservice'}}
        if as_group == 'autoscale-blue':
            return {'elb_online': {'instance_blue1': 'inservice'}}
        raise Exception("get_elb_instance_status_autoscaling_group : auto scale parameter is not correct")
    get_elb_instance_status_autoscaling_group.side_effect = get_eisag_behavior

    def get_asgapts_behavior(as_conn, app, log_file):
        if app == green_app:
            return 'asg_green', ['suspend_process']
        if app == blue_app:
            return 'asg_blue', []
        raise Exception("get_autoscaling_group_and_processes_to_suspend : application parameter is not correct")
    get_autoscaling_group_and_processes_to_suspend.side_effect = get_asgapts_behavior

    # Launching command
    swap_cmd = Swapbluegreen(worker)
    swap_cmd.execute()

    # Check that everything has gone as planned
    assert get_blue_green_apps.called == 1

    assert suspend_autoscaling_group_processes.call_count == 2
    suspend_autoscaling_group_processes.assert_has_calls([
        call(connection_mock, 'asg_green', ['suspend_process'], 'log_file'),
        call(connection_mock, 'asg_blue', [], 'log_file')
    ], True)

    assert resume_autoscaling_group_processes.call_count == 2
    resume_autoscaling_group_processes.assert_has_calls([
        call(connection_mock, 'asg_green', ['suspend_process'], 'log_file'),
        call(connection_mock, 'asg_blue', [], 'log_file')
    ], True)

    assert register_all_instances_to_elb.call_count == 2
    register_all_instances_to_elb.assert_has_calls([
        call(connection_mock, ['elb_online'], {'elb_temp': {'instance_green1': 'inservice'}}, 'log_file'),
        call(connection_mock, ['elb_temp'],  {'elb_online': {'instance_blue1': 'inservice'}}, 'log_file')
    ], False)

    assert deregister_all_instances_from_elb.call_count == 2
    deregister_all_instances_from_elb.assert_has_calls([
        call(connection_mock, {'elb_online': {'instance_blue1': 'inservice'}}, 'log_file'),
        call(connection_mock, {'elb_temp': {'instance_green1': 'inservice'}}, 'log_file')
    ], False)
