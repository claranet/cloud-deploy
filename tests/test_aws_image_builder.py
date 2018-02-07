import json
import tempfile
import mock
import os
import shutil
import yaml

from libs.image_builder_aws import AWSImageBuilder
from pypacker import PACKER_JSON_PATH
from tests.helpers import LOG_FILE, mocked_logger, get_test_application, get_test_config, void


@mock.patch('pypacker.log', new=mocked_logger)
@mock.patch('libs.image_builder_aws.log', new=mocked_logger)
@mock.patch('libs.image_builder.log', new=mocked_logger)
@mock.patch('libs.provisioner.log', new=mocked_logger)
@mock.patch('libs.provisioner_ansible.log', new=mocked_logger)
@mock.patch('libs.provisioner.FeaturesProvisioner._get_provisioner_repo', new=void)  # We do not test git mirroring here
@mock.patch('libs.provisioner.FeaturesProvisioner._get_local_repo_path')
@mock.patch('libs.provisioner_ansible.gcall')
@mock.patch('pypacker.Packer._run_packer_cmd')
def test_build_image_ansible(packer_run_packer_cmd, gcall, provisioner_get_local_repo_path):
    # Application context
    app = get_test_application()
    job = {
        "_id": "test_job_id",
        "app_id": "test_app_id",
        "command": "buildimage",
        "instance_type": "test_instance_type",
        "options": [False]  # Do not skip bootstrap
    }
    test_config = get_test_config(
        features_provisioners={'ansible': {
            'git_revision': 'master',
            'git_repo': 'my_ansible_repo',
            'base_playbook_file': 'tests/provisioners_data/base_playbook.yml',
            'base_playbook_requirements_file': 'tests/provisioners_data/base_requirements.yml',
        }})
    del test_config['features_provisioners']['salt']

    # Mocks
    packer_run_packer_cmd.return_value = (0, "something:test_ami_id")

    tmp_dir = tempfile.mkdtemp()
    venv_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.tox/py27/bin/')
    shutil.copyfile(
        os.path.join(os.path.dirname(__file__), 'provisioners_data', 'requirements.yml'),
        os.path.join(tmp_dir, 'requirements.yml'))
    provisioner_get_local_repo_path.return_value = tmp_dir

    # Build image
    with mock.patch('ghost_tools.config', new=test_config):
        image_builder = AWSImageBuilder(app, job, None, LOG_FILE, test_config)
        ami_id, ami_name = image_builder.start_builder()

    # Test
    assert ami_id == "test_ami_id"
    assert ami_name.startswith("ami.test.eu-west-1.webfront.test-app.")

    gcall.assert_called_once_with(
        "{0}ansible-galaxy install -r {1}/requirement_app.yml -p {1}/roles".format(venv_dir, tmp_dir),
        'Ansible -  ansible-galaxy command', LOG_FILE)

    with open(os.path.join(PACKER_JSON_PATH, job['_id'] + '.json'), 'r') as f:
        # Verify generated ansible files
        with open(os.path.join(tmp_dir, 'requirement_app.yml'), 'r') as f2:
            requirement_app = yaml.load(f2)
            assert requirement_app == [
                {"src": "base-role-src", "version": "base-role-version"},
                {"name": "feature-ansible", "scm": "test-scm", "src": "test-src", "version": "test-version"}]

        with open(os.path.join(tmp_dir, 'main.yml'), 'r') as f3:
            playbook = yaml.load(f3)
            assert playbook == [
                {"name": "Base playbook", "hosts": "all", "roles": ['ansible-base-role']},
                {"name": "Ghost application features", "hosts": "all",
                 "roles": [{"role": "feature-ansible", "feature-property": "property"}]}]

        # Verify packer config
        packer_config = json.load(f)
        assert packer_config == {
            "provisioners": [
                {
                    "type": "shell",
                    "environment_vars": [
                        "GHOST_APP=test-app",
                        "GHOST_ENV=test",
                        "GHOST_ENV_COLOR=",
                        "GHOST_ROLE=webfront",
                        "EMPTY_ENV="
                    ],
                    "script": "/ghost/test-app/test/webfront/hook-pre_buildimage"
                },
                {
                    "type": "ansible",
                    "playbook_file": os.path.join(tmp_dir, "main.yml"),
                    "ansible_env_vars": [ "ANSIBLE_HOST_KEY_CHECKING=False", "ANSIBLE_FORCE_COLOR=1", "PYTHONUNBUFFERED=1", "ANSIBLE_ROLES_PATH={}".format(tmp_dir)],
                    "user": "admin",
                    "command": os.path.join(venv_dir, "ansible-playbook"),
                    "extra_arguments": ['-v'],
                },
                {
                    "type": "shell",
                    "environment_vars": [
                        "GHOST_APP=test-app",
                        "GHOST_ENV=test",
                        "GHOST_ENV_COLOR=",
                        "GHOST_ROLE=webfront",
                        "EMPTY_ENV="
                    ],
                    "script": "/ghost/test-app/test/webfront/hook-post_buildimage"
                }
            ],
            "builders": [
                {
                    "ami_block_device_mappings": [],
                    "launch_block_device_mappings": [],
                    "source_ami": "ami-source",
                    "tags": {
                        "Name": "ec2.name.test",
                        "tag-name": "tag-value",
                    },
                    "subnet_id": "subnet-test",
                    "ssh_username": "admin",
                    "ssh_private_ip": True,
                    "region": "eu-west-1",
                    "security_group_ids": [
                        "sg-test"
                    ],
                    "ami_name": ami_name,
                    "iam_instance_profile": "iam.profile.test",
                    "instance_type": "test_instance_type",
                    "associate_public_ip_address": True,
                    "vpc_id": "vpc-test",
                    "type": "amazon-ebs",
                    "ssh_pty": True
                }
            ]
        }


@mock.patch('pypacker.log', new=mocked_logger)
@mock.patch('libs.image_builder_aws.log', new=mocked_logger)
@mock.patch('libs.image_builder.log', new=mocked_logger)
@mock.patch('libs.provisioner.log', new=mocked_logger)
@mock.patch('libs.provisioner_ansible.log', new=mocked_logger)
@mock.patch('libs.provisioner.FeaturesProvisioner._get_provisioner_repo', new=void)  # We do not test git mirroring here
@mock.patch('libs.provisioner.FeaturesProvisioner._get_local_repo_path')
@mock.patch('libs.provisioner_ansible.gcall')
@mock.patch('pypacker.Packer._run_packer_cmd')
def test_build_image_ansible_debug(packer_run_packer_cmd, gcall, provisioner_get_local_repo_path):
    # Application context
    app = get_test_application()
    job = {
        "_id": "test_job_id",
        "app_id": "test_app_id",
        "command": "buildimage",
        "instance_type": "test_instance_type",
        "options": [False]  # Do not skip bootstrap
    }
    test_config = get_test_config(
        features_provisioners={'ansible': {
            'git_revision': 'master',
            'git_repo': 'my_ansible_repo',
            'base_playbook_file': 'tests/provisioners_data/base_playbook.yml',
            'base_playbook_requirements_file': 'tests/provisioners_data/base_requirements.yml',
        }},
        provisioner_log_level='debug')
    del test_config['features_provisioners']['salt']

    # Mocks
    packer_run_packer_cmd.return_value = (0, "something:test_ami_id")

    tmp_dir = tempfile.mkdtemp()
    venv_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.tox/py27/bin/')
    shutil.copyfile(
        os.path.join(os.path.dirname(__file__), 'provisioners_data', 'requirements.yml'),
        os.path.join(tmp_dir, 'requirements.yml'))
    provisioner_get_local_repo_path.return_value = tmp_dir

    # Build image
    with mock.patch('ghost_tools.config', new=test_config):
        image_builder = AWSImageBuilder(app, job, None, LOG_FILE, test_config)
        ami_id, ami_name = image_builder.start_builder()

    # Test
    assert ami_id == "test_ami_id"
    assert ami_name.startswith("ami.test.eu-west-1.webfront.test-app.")

    gcall.assert_called_once_with(
        "{0}ansible-galaxy install -r {1}/requirement_app.yml -p {1}/roles".format(venv_dir, tmp_dir),
        'Ansible -  ansible-galaxy command', LOG_FILE)

    with open(os.path.join(PACKER_JSON_PATH, job['_id'] + '.json'), 'r') as f:
        # Verify generated ansible files
        with open(os.path.join(tmp_dir, 'requirement_app.yml'), 'r') as f2:
            requirement_app = yaml.load(f2)
            assert requirement_app == [
                {"src": "base-role-src", "version": "base-role-version"},
                {"name": "feature-ansible", "scm": "test-scm", "src": "test-src", "version": "test-version"}]

        with open(os.path.join(tmp_dir, 'main.yml'), 'r') as f3:
            playbook = yaml.load(f3)
            assert playbook == [
                {"name": "Base playbook", "hosts": "all", "roles": ['ansible-base-role']},
                {"name": "Ghost application features", "hosts": "all",
                 "roles": [{"role": "feature-ansible", "feature-property": "property"}]}]

        # Verify packer config
        packer_config = json.load(f)
        assert packer_config == {
            "provisioners": [
                {
                    "type": "shell",
                    "environment_vars": [
                        "GHOST_APP=test-app",
                        "GHOST_ENV=test",
                        "GHOST_ENV_COLOR=",
                        "GHOST_ROLE=webfront",
                        "EMPTY_ENV="
                    ],
                    "script": "/ghost/test-app/test/webfront/hook-pre_buildimage"
                },
                {
                    "type": "ansible",
                    "playbook_file": os.path.join(tmp_dir, "main.yml"),
                    "ansible_env_vars": [ "ANSIBLE_HOST_KEY_CHECKING=False", "ANSIBLE_FORCE_COLOR=1", "PYTHONUNBUFFERED=1", "ANSIBLE_ROLES_PATH={}".format(tmp_dir)],
                    "user": "admin",
                    "command": os.path.join(venv_dir, "ansible-playbook"),
                    "extra_arguments": ['-vvv'],
                },
                {
                    "type": "shell",
                    "environment_vars": [
                        "GHOST_APP=test-app",
                        "GHOST_ENV=test",
                        "GHOST_ENV_COLOR=",
                        "GHOST_ROLE=webfront",
                        "EMPTY_ENV="
                    ],
                    "script": "/ghost/test-app/test/webfront/hook-post_buildimage"
                }
            ],
            "builders": [
                {
                    "ami_block_device_mappings": [],
                    "launch_block_device_mappings": [],
                    "source_ami": "ami-source",
                    "tags": {
                        "Name": "ec2.name.test",
                        "tag-name": "tag-value",
                    },
                    "subnet_id": "subnet-test",
                    "ssh_username": "admin",
                    "ssh_private_ip": True,
                    "region": "eu-west-1",
                    "security_group_ids": [
                        "sg-test"
                    ],
                    "ami_name": ami_name,
                    "iam_instance_profile": "iam.profile.test",
                    "instance_type": "test_instance_type",
                    "associate_public_ip_address": True,
                    "vpc_id": "vpc-test",
                    "type": "amazon-ebs",
                    "ssh_pty": True
                }
            ]
        }
