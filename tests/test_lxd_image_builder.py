import mock
import os

from libs.builders.image_builder_lxd import LXDImageBuilder
from tests.helpers import LOG_FILE, mocked_logger, get_test_application, get_test_config, void


@mock.patch('libs.builders.image_builder_lxd.log', new=mocked_logger)
@mock.patch('libs.builders.image_builder.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('libs.builders.image_builder_lxd.time.sleep', new=void)  # Avoid waiting
@mock.patch('libs.builders.image_builder_lxd.LXDClient')
def test_build_image(lxd_client_cls):
    # Application context
    app = get_test_application()
    job = {
        "_id": "test_job_id",
        "app_id": "test_app_id",
        "command": "buildimage",
        "instance_type": "test_instance_type",
        "options": [False]  # Do not skip bootstrap
    }
    job["id"] = "012345678901234567890123"

    test_config = get_test_config(
        features_provisioners={'ansible': {
            'git_revision': 'master',
            'git_repo': 'my_ansible_repo',
            'base_playbook_file': 'tests/provisioners_data/base_playbook.yml',
            'base_playbook_requirements_file': 'tests/provisioners_data/base_requirements.yml',
        }})
    provisioners = []

    # Mocks
    lxd_client = mock.MagicMock()
    lxd_client_cls.return_value = lxd_client
    lxd_containers_mock = lxd_client.containers
    lxd_profiles_mock = lxd_client.profiles

    lxd_container_mock = mock.MagicMock()
    lxd_client.containers.create.return_value = lxd_container_mock
    valid_execution_mock = mock.MagicMock()
    valid_execution_mock.exit_code = 0
    valid_execution_mock.stdout = 'STDOUT'
    valid_execution_mock.stderr = 'STDERR'
    lxd_container_mock.execute.return_value = valid_execution_mock

    lxd_client.images.all.return_value = []

    venv_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.tox/py27')
    venv_bin_dir = os.path.join(venv_dir, 'bin')

    # Build image
    with mock.patch('ghost_tools.config', new=test_config):
        image_builder = LXDImageBuilder(app, job, None, LOG_FILE, test_config)
        image_builder.set_source_hooks('/source-hook-path')
        image_builder.start_builder()

    # Test
    container_name = image_builder._container_name
    assert container_name.startswith("ami-test-eu-west-1-webfront-test-app-")
    expected_container_config = {
        'source': {
            "type": "image",
            "protocol": "lxd",
            "mode": "pull",
            "fingerprint": "lxd-container-image-test",
            "server": "http://lxd-image-endpoint:1234",
        },
        'config': {"security.privileged": 'True'},
        'ephemeral': False,
        'name': container_name,
        'profiles': ["default", container_name],
    }

    lxd_containers_mock.create.assert_called_once_with(expected_container_config, wait=True)

    lxd_container_mock.start.assert_called_once_with(wait=True)
    lxd_container_mock.stop.assert_called_once_with(wait=True)

    lxd_container_mock.execute.assert_any_call(["sh", "/ghost/hook-pre_buildimage"])
    lxd_container_mock.execute.assert_any_call(["sh", "/ghost/hook-post_buildimage"])

    lxd_container_mock.execute.assert_any_call(
            [os.path.join(venv_bin_dir, "ansible-playbook"), "-i", "localhost,",
             "--connection=local", "/srv/ansible/main.yml", "-v"])
    lxd_container_mock.execute.assert_any_call(
        ["salt-call", "state.highstate", "--file-root=/srv/salt/salt",
         "--pillar-root=/srv/salt/pillar ", "--local", "-l", "info"])

    expected_devices_config = {
        'venv': {
            'path': venv_dir,
            'source': venv_dir,
            'type': 'disk',
        },
        'salt': {
            'path': '/srv/salt',
            'source': "/tmp/ghost-features-provisioner/salt-test_job_id",
            'type': 'disk'
        },
        'ansible': {
            'path': '/srv/ansible',
            'source': "/tmp/ghost-features-provisioner/ansible-test_job_id",
            'type': 'disk'
        },
        'hooks': {
            'path': "/ghost",
            'source': "/source-hook-path",
            'type': 'disk'
        },
    }
    lxd_profiles_mock.create.assert_called_once_with(container_name, devices=expected_devices_config)
    lxd_containers_mock.snapshots.create(container_name, stateful=False, wait=True)
    snapshot = lxd_containers_mock.snapshots.get(container_name)
    lxd_containers_mock.snapshots.get(container_name)
    snapshot.publish(wait=True)
    snapshot.delete(wait=True)


@mock.patch('libs.builders.image_builder_lxd.log', new=mocked_logger)
@mock.patch('libs.builders.image_builder.log', new=mocked_logger)
@mock.patch('ghost_tools.log', new=mocked_logger)
@mock.patch('libs.builders.image_builder_lxd.time.sleep', new=void)  # Avoid waiting
@mock.patch('libs.builders.image_builder_lxd.LXDClient')
def test_purge(lxd_client_cls):
    # Application context
    app = get_test_application()

    job = {
        "_id": "test_job_id",
        "app_id": "test_app_id",
        "command": "buildimage",
        "instance_type": "test_instance_type",
        "options": [False]  # Do not skip bootstrap
    }
    job["id"] = "012345678901234567890123"

    test_config = get_test_config(ami_retention=3)

    # Mocks
    lxd_client = mock.MagicMock()
    lxd_client_cls.return_value = lxd_client
    lxd_image = mock.MagicMock()
    lxd_client.images.all.return_value = [lxd_image for i in range(0, 6)]

    # Purge images
    with mock.patch('ghost_tools.config', new=test_config):
        image_builder = LXDImageBuilder(app, job, None, LOG_FILE, test_config)
        image_builder.purge_old_images()

    # Test
    assert lxd_image.delete.call_count == 3
