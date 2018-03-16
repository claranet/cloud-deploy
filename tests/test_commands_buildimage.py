from mock import mock, MagicMock, call

from commands.buildimage import Buildimage
from tests.helpers import get_test_application, mocked_logger, LOG_FILE, void


@mock.patch('commands.buildimage.lxd_is_available')
@mock.patch('commands.buildimage.LXDImageBuilder')
@mock.patch('commands.buildimage.AWSImageBuilder')
@mock.patch('commands.buildimage.create_userdata_launchconfig_update_asg', new=lambda a, b, c, d, e: True)
@mock.patch('commands.buildimage.touch_app_manifest', new=void)
@mock.patch('commands.buildimage.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('ghost_aws.log', new=mocked_logger)
def test_buildimage_ami(awsimagebuilder_mock, lxdimagebuilder_mock, lxd_is_available_mock):
    """
    Test AWS AMI basic ok
    """
    # Set up mocks and variables
    test_app = get_test_application()

    worker = MagicMock()
    worker.app = test_app
    worker.log_file = LOG_FILE

    def assert_ok(status, message=None):
        assert status == "done", "Status is {} and not done : {}".format(status, message)
    worker.update_status = assert_ok

    lxd_is_available_mock.return_value = False

    # Launching command
    cmd = Buildimage(worker)
    cmd._update_app_ami = void
    cmd._aws_image_builder.start_builder.return_value = "ami_id", "ami_name"
    cmd.execute()

    assert awsimagebuilder_mock.call_count == 1
    assert lxdimagebuilder_mock.call_count == 0


@mock.patch('commands.buildimage.lxd_is_available')
@mock.patch('commands.buildimage.LXDImageBuilder')
@mock.patch('commands.buildimage.AWSImageBuilder')
@mock.patch('commands.buildimage.create_userdata_launchconfig_update_asg', new=lambda a, b, c, d, e: True)
@mock.patch('commands.buildimage.touch_app_manifest', new=void)
@mock.patch('commands.buildimage.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('ghost_aws.log', new=mocked_logger)
def test_buildimage_ami_error(awsimagebuilder_mock, lxdimagebuilder_mock, lxd_is_available_mock):
    """
    Test build AWS AMI is failed
    """
    # Set up mocks and variables
    test_app = get_test_application()

    worker = MagicMock()
    worker.app = test_app
    worker.log_file = LOG_FILE

    def assert_failed(status, message=None):
        assert status == "failed", "Status is {} and not failed: {}".format(status, message)
    worker.update_status = assert_failed

    lxd_is_available_mock.return_value = False

    # Launching command
    cmd = Buildimage(worker)
    cmd._update_app_ami = void
    cmd._aws_image_builder.start_builder.return_value = "ERROR", "ERROR"
    cmd.execute()

    assert awsimagebuilder_mock.call_count == 1
    assert lxdimagebuilder_mock.call_count == 0


@mock.patch('commands.buildimage.lxd_is_available')
@mock.patch('commands.buildimage.LXDImageBuilder')
@mock.patch('commands.buildimage.AWSImageBuilder')
@mock.patch('commands.buildimage.create_userdata_launchconfig_update_asg', new=lambda a, b, c, d, e: True)
@mock.patch('commands.buildimage.touch_app_manifest', new=void)
@mock.patch('commands.buildimage.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('ghost_aws.log', new=mocked_logger)
def test_buildimage_ami_error_with_lxd(awsimagebuilder_mock, lxdimagebuilder_mock, lxd_is_available_mock):
    """
    Test build AWS AMI is failed
    """
    # Set up mocks and variables
    test_app = get_test_application()

    worker = MagicMock()
    worker.app = test_app
    worker.log_file = LOG_FILE

    def assert_failed(status, message=None):
        assert status == "failed", "Status is {} and not failed: {}".format(status, message)
    worker.update_status = assert_failed

    lxd_is_available_mock.return_value = True

    # Launching command
    cmd = Buildimage(worker)
    cmd._update_app_ami = void
    cmd._update_container_source = void
    cmd._aws_image_builder.start_builder.return_value = "ERROR", "ERROR"
    cmd.execute()

    assert awsimagebuilder_mock.call_count == 1
    assert lxdimagebuilder_mock.call_count == 1


@mock.patch('commands.buildimage.lxd_is_available')
@mock.patch('commands.buildimage.LXDImageBuilder')
@mock.patch('commands.buildimage.AWSImageBuilder')
@mock.patch('commands.buildimage.create_userdata_launchconfig_update_asg', new=lambda a, b, c, d, e: True)
@mock.patch('commands.buildimage.touch_app_manifest', new=void)
@mock.patch('commands.buildimage.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('ghost_aws.log', new=mocked_logger)
def test_buildimage_lxd(AWSImageBuilder_mock, LXDImageBuilder_mock, lxd_is_available_mock):
    """
    Test LXD Image Build
    """
    # Set up mocks and variables
    test_app = get_test_application()
    test_app['build_infos']['source_container_image'] = 'dummy_lxc_source_image'

    worker = MagicMock()
    worker.app = test_app
    worker.log_file = LOG_FILE

    def assert_ok(status, message=None):
        assert status == "done", "Status is {} and not done : {}".format(status, message)
    worker.update_status = assert_ok

    lxd_is_available_mock.return_value = True

    # Launching command
    cmd = Buildimage(worker)
    cmd._update_app_ami = void
    cmd._update_container_source = void
    cmd._aws_image_builder.start_builder.return_value = "ami_id", "ami_name"
    cmd.execute()

    assert AWSImageBuilder_mock.call_count == 1
    assert LXDImageBuilder_mock.call_count == 1
