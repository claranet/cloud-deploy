from mock import mock, MagicMock, call

from commands.executescript import Executescript
from tests.helpers import get_test_application, get_dummy_bash_script, mocked_logger, LOG_FILE


@mock.patch('commands.executescript.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('ghost_aws.log', new=mocked_logger)
def test_executescript_cmd_abort():
    """
    Test missing mandatory options
    """
    # Set up mocks and variables
    test_app = get_test_application()

    worker = MagicMock()
    worker.app = test_app
    worker.log_file = LOG_FILE
    worker._config = {'enable_executescript_command': 'true'}

    def assert_aborted(status, message=None):
        assert status == "aborted", "Status is {} and not done : {}".format(status, message)
    worker.update_status = assert_aborted

    # Launching command
    cmd = Executescript(worker)
    cmd.execute()


@mock.patch('commands.executescript.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('ghost_aws.log', new=mocked_logger)
def test_executescript_cmd_abort_disabled():
    """
    Test missing mandatory options
    """
    # Set up mocks and variables
    test_app = get_test_application()

    worker = MagicMock()
    worker.app = test_app
    worker.log_file = LOG_FILE

    def assert_aborted(status, message=None):
        assert status == "aborted", "Status is {} and not done : {}".format(status, message)
    worker.update_status = assert_aborted

    # Launching command
    cmd = Executescript(worker)
    cmd.execute()


@mock.patch('commands.executescript.cloud_connections')
@mock.patch('commands.executescript.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('ghost_aws.log', new=mocked_logger)
def test_executescript_cmd_single_host(cloud_connections):
    """
    Test basic flow with 'single' Host option
    """
    # Set up mocks and variables
    test_app = get_test_application()

    connection_mock = MagicMock()
    connection_pool = MagicMock()
    cloud_connections.get.return_value.return_value = connection_pool
    connection_pool.get_connection.return_value = connection_mock

    worker = MagicMock()
    worker.app = test_app
    worker.log_file = LOG_FILE
    worker._config = {'enable_executescript_command': 'true'}
    worker.job = {
        'options': [
            get_dummy_bash_script(True),
            '',
            'single',
            '10.0.0.1',
        ],
        '_id': '42',
        'user': 'gogo'
    }

    def assert_done(status, message=None):
        assert status == "done", "Status is {} and not done : {}".format(status, message)
    worker.update_status = assert_done

    def assert_exec_single(script, module_name, single_host_ip):
        assert single_host_ip == '10.0.0.1', "Single_host_ip {} is not valid".format(single_host_ip)

    # Launching command
    cmd = Executescript(worker)
    cmd._exec_script_single_host = assert_exec_single
    cmd.execute()


@mock.patch('commands.executescript.launch_executescript')
@mock.patch('commands.executescript.cloud_connections')
@mock.patch('commands.executescript.get_ec2_instance')
@mock.patch('commands.executescript.get_ghost_env_variables')
@mock.patch('commands.executescript.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('ghost_aws.log', new=mocked_logger)
def test_executescript_cmd_single_host_deep(get_ghost_env_variables,
                                            get_ec2_instance,
                                            cloud_connections,
                                            launch_executescript,
                                            ):
    """
    Test _exec_script_single_host internal call when using option "single" Host
    """
    # Set up mocks and variables
    test_app = get_test_application()

    connection_mock = MagicMock()
    connection_pool = MagicMock()
    cloud_connections.get.return_value.return_value = connection_pool
    connection_pool.get_connection.return_value = connection_mock

    worker = MagicMock()
    worker.app = test_app
    worker.log_file = LOG_FILE
    worker._config = {'enable_executescript_command': 'true'}
    worker.job = {
        'options': [
            get_dummy_bash_script(True),
            '',
            'single',
            '10.0.0.1',
        ],
        '_id': '42',
        'user': 'gogo'
    }

    def assert_done(status, message=None):
        assert status == "done", "Status is {} and not done : {}".format(status, message)
    worker.update_status = assert_done

    get_ec2_instance.return_value = type('X', (object,), {
        'id': 'myid',
        'vpc_id': test_app['vpc_id'],
        'private_ip_address': '10.0.0.1',
        'tags': {
            'app': test_app['name'],
            'env': test_app['env'],
            'role': test_app['role'],
        },
    })()

    get_ghost_env_variables.return_value = {}

    # Launching command
    cmd = Executescript(worker)
    cmd.execute()

    # Check that everything has gone as planned
    assert get_ec2_instance.called == 1
    assert launch_executescript.called == 1
    assert get_ghost_env_variables.called == 1

    get_ghost_env_variables.assert_called_once_with(
        test_app, None, worker.job['user']
    )

    get_ec2_instance.assert_called_once_with(
        connection_pool, test_app['region'], {
            'private-ip-address': '10.0.0.1',
            'vpc-id': test_app['vpc_id'],
        }
    )

    launch_executescript.assert_called_once_with(
        test_app, get_dummy_bash_script(), '/tmp', 0, '42', ['10.0.0.1'], 'serial', LOG_FILE, {})


@mock.patch('commands.executescript.cloud_connections')
@mock.patch('commands.executescript.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('ghost_aws.log', new=mocked_logger)
def test_executescript_cmd(cloud_connections):
    """
    Test standard execution flow (with Serial option)
    """
    # Set up mocks and variables
    test_app = get_test_application()

    connection_mock = MagicMock()
    connection_pool = MagicMock()
    cloud_connections.get.return_value.return_value = connection_pool
    connection_pool.get_connection.return_value = connection_mock

    worker = MagicMock()
    worker.app = test_app
    worker.log_file = LOG_FILE
    worker._config = {'enable_executescript_command': 'true'}
    worker.job = {
        'options': [
            get_dummy_bash_script(True),
            '',
            'serial',
            '1by1',
        ],
        '_id': '42',
        'user': 'gogo'
    }

    def assert_done(status, message=None):
        assert status == "done", "Status is {} and not done : {}".format(status, message)
    worker.update_status = assert_done

    def assert_exec(script, module_name, fabric_execution_strategy, safe_deployment_strategy):
        assert fabric_execution_strategy == 'serial' and safe_deployment_strategy == '1by1',\
            "fabric_execution_strategy {} or safe_deployment_strategy {} is not valid".format(fabric_execution_strategy, safe_deployment_strategy)

    # Launching command
    cmd = Executescript(worker)
    cmd._exec_script = assert_exec
    cmd.execute()


@mock.patch('commands.executescript.HostDeploymentManager')
@mock.patch('commands.executescript.get_ghost_env_variables')
@mock.patch('commands.executescript.cloud_connections')
@mock.patch('commands.executescript.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('ghost_aws.log', new=mocked_logger)
def test_executescript_cmd_deep(cloud_connections,
                                get_ghost_env_variables,
                                HostDeploymentManager,):
    """
    Test standard execution flow (with Serial option), deep dive on _exec_script flow
    """
    # Set up mocks and variables
    test_app = get_test_application()

    connection_mock = MagicMock()
    connection_pool = MagicMock()
    cloud_connections.get.return_value.return_value = connection_pool
    connection_pool.get_connection.return_value = connection_mock

    worker = MagicMock()
    worker.app = test_app
    worker.log_file = LOG_FILE
    worker._config = {'enable_executescript_command': 'true'}
    worker.job = {
        'options': [
            get_dummy_bash_script(True),
            '',
            'serial',
            '1by1',
        ],
        '_id': '42',
        'user': 'gogo'
    }

    get_ghost_env_variables.return_value = {}

    def assert_done(status, message=None):
        assert status == "done", "Status is {} and not done : {}".format(status, message)
    worker.update_status = assert_done

    # Launching command
    cmd = Executescript(worker)
    cmd.execute()

    # Check that everything has gone as planned
    assert get_ghost_env_variables.called == 1
    assert HostDeploymentManager.called == 1

    get_ghost_env_variables.assert_called_once_with(
        test_app, None, worker.job['user']
    )

    HostDeploymentManager.assert_called_once_with(
        connection_pool, test_app, None, LOG_FILE,
        test_app['safe-deployment'], 'serial',
        'executescript', {
            'script': get_dummy_bash_script(),
            'context_path': '/tmp',
            'sudoer_uid': 0,
            'jobid': worker.job['_id'],
            'env_vars': {},
        })
