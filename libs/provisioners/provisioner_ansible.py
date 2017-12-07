import os
import copy
import yaml
import sys
from fabric.colors import yellow as _yellow, red as _red

from ghost_log import log
from ghost_tools import gcall
from .provisioner import FeaturesProvisioner, GalaxyNoMatchingRolesException, GalaxyBadRequirementPathException

ANSIBLE_BASE_PLAYBOOK = {'name': 'Ghost application features', 'hosts': 'all', 'roles': []}
ANSIBLE_COMMAND = "bin/ansible-playbook"
ANSIBLE_GALAXY_DEFAULT_CMD_PATH = "bin/ansible-galaxy"
ANSIBLE_ENV_VARS = ["ANSIBLE_HOST_KEY_CHECKING=False", "ANSIBLE_FORCE_COLOR=1", "PYTHONUNBUFFERED=1"]
ANSIBLE_LOG_LEVEL_MAP = {"info": "-v", "profile": "-vv", "debug": "-vvv", "trace": "-vvvv", "garbage": "-vvvv", "all": "-vvvv"}


class FeaturesProvisionerAnsible(FeaturesProvisioner):
    """ Build features with ansible """
    def __init__(self, log_file, unique_id, options, config, global_config):
        FeaturesProvisioner.__init__(self, log_file, 'ansible', unique_id, options, config, global_config)
        ghost_root_path = global_config.get('ghost_root_path', '/usr/local/share/ghost')
        self._ansible_playbook_path = os.path.join(self.local_repo_path, 'main.yml')
        self._ansible_galaxy_role_path = os.path.join(self.local_repo_path, 'roles')
        self._ansible_requirement_app = os.path.join(self.local_repo_path, 'requirement_app.yml')
        self._ansible_galaxy_rq_path = os.path.join(self.local_repo_path,
                                                    config.get('ansible_galaxy_requirements_path', 'requirements.yml'))
        self._ansible_galaxy_command_path = os.path.join(sys.exec_prefix, ANSIBLE_GALAXY_DEFAULT_CMD_PATH)
        self._ansible_command_path = os.path.join(sys.exec_prefix, ANSIBLE_COMMAND)
        self._ansible_env_vars = ANSIBLE_ENV_VARS + ["ANSIBLE_ROLES_PATH={}".format(self.local_repo_path)]

        self._ansible_base_playbook_file = os.path.join(
            ghost_root_path,
            config.get('base_playbook_file', 'ansible-playbook-ghost-common/ghost-common.yml'))
        self._ansible_base_requirements_file = os.path.join(
            ghost_root_path,
            config.get('base_playbook_requirements_file', 'ansible-playbook-ghost-common/requirements.yml'))

        self._provisioner_log_level = self.global_config.get('provisioner_log_level', 'info')

    def build_packer_provisioner_config(self, features):
        features = self._format_provisioner_features(features)
        self.build_provisioner_features_files(features)
        _log_level = ANSIBLE_LOG_LEVEL_MAP.get(self._provisioner_log_level, None)
        _provisioner_config = {
            'type': 'ansible',
            'playbook_file': self._ansible_playbook_path,
            'ansible_env_vars': self._ansible_env_vars,
            'user': self._options,
            'command': self._ansible_command_path,
        }
        if _log_level is not None:
            _provisioner_config['extra_arguments'] = [_log_level]
        return [_provisioner_config]

    def build_provisioner_features_files(self, features):
        self._build_ansible_galaxy_requirement(features)
        self._build_ansible_playbook(features)

    def _build_ansible_playbook(self, features):
        """ Write ansible playbook from application features """
        with open(self._ansible_playbook_path, "w") as stream_features:
            log("Ansible - Writing playbook: {0}".format(self._ansible_playbook_path), self._log_file)
            log(_yellow("Ansible - features: {0}".format(features[-1]['roles'])), self._log_file)
            try:
                yaml.safe_dump(features, stream_features, default_flow_style=False, explicit_start=True, allow_unicode=True)
            except yaml.YAMLError as exc:
                log(_red("Ansible - ERROR Writing playbook: {0}".format(exc)), self._log_file)
                raise

    def _get_ansible_roles(self, features):
        """ Get role list with unique role

        >>> features = [{'hosts': 'all', 'roles': [{'role': 'package', 'package_name': ['git_vim']}, {'role': 'package', 'package_name': ['curl']}, {'role': 'apache2', 'hostname': 'localhost'}]}]
        >>> import pprint
        >>> pprint.pprint(sorted(FeaturesProvisionerAnsible(None, None, {}, {}, {})._get_ansible_roles(features)))
        ['apache2', 'package']

        >>> features = [{'hosts': 'all', 'roles': []}]
        >>> pprint.pprint(sorted(FeaturesProvisionerAnsible(None, None, {}, {}, {})._get_ansible_roles(features)))
        []

        """
        return list(set([r['role'] for r in features[-1]['roles']]))

    def _get_roles_from_requirement(self, role):
        """ Return only galaxy roles (yaml document) needed from application """
        if os.path.exists(self._ansible_galaxy_rq_path):
            with open(self._ansible_galaxy_rq_path, 'r') as stream_requirement:
                requirements_yaml = yaml.load_all(stream_requirement)
                for requirement in requirements_yaml:
                    for feature in requirement:
                        if feature['name'] == role:
                            return feature
        else:
            raise GalaxyBadRequirementPathException(
                "Ansible - ERROR: galaxy requirement path doesn't exist check file name on repository : {0}".format(
                    self._ansible_galaxy_rq_path))

    def _build_ansible_galaxy_requirement(self, features):
        """ Generates ansible galaxy requirement file from features """
        with open(self._ansible_base_requirements_file, 'r') as requirements_file:
            requirement_app = yaml.load(requirements_file)
        for role in self._get_ansible_roles(features):
            requirement_app.append(self._get_roles_from_requirement(role))
        if requirement_app != [None]:
            with open(self._ansible_requirement_app, "w") as stream_requirement_app:
                yaml.dump(requirement_app, stream_requirement_app, default_flow_style=False)
            log("Ansible - Getting roles from : {0}".format(self._ansible_galaxy_rq_path), self._log_file)
            gcall("{} install -r {} -p {}".format(
                    self._ansible_galaxy_command_path,
                    self._ansible_requirement_app,
                    self._ansible_galaxy_role_path),
                'Ansible -  ansible-galaxy command',
                self._log_file)
        else:
            raise GalaxyNoMatchingRolesException(
                "Ansible - ERROR: No roles match galaxy requirements for one or more features {0}".format(
                    features[-1]['roles']))

    def build_packer_provisioner_cleanup(self):
        return None


    def _format_provisioner_features(self, features):
        """ Generates the role dictionnary object with all required features and their options

        >>> features = [{'name': 'package', 'version': 'package_name=git_vim', 'provisioner': 'ansible'},
        ...             {'name': 'package', 'version': 'package_name=curl', 'provisioner': 'ansible'}]
        >>> global_config = {'ghost_root_path': os.path.abspath(os.path.dirname(sys.argv[0]))}
        >>> import pprint
        >>> pprint.pprint(FeaturesProvisionerAnsible(None, None, {}, {}, global_config)._format_provisioner_features(features)[-1])
        {'hosts': 'all',
         'name': 'Ghost application features',
         'roles': [{'package_name': 'git_vim', 'role': 'package'},
                   {'package_name': 'curl', 'role': 'package'}]}

        >>> features = [{'name': 'package', 'version': 'package_name=git_vim', 'provisioner': 'salt'},
        ...             {'name': 'package', 'version': 'package_name=curl', 'provisioner': 'ansible'}]
        >>> pprint.pprint(FeaturesProvisionerAnsible(None, None, {}, {}, global_config)._format_provisioner_features(features)[-1])
        {'hosts': 'all',
         'name': 'Ghost application features',
         'roles': [{'package_name': 'curl', 'role': 'package'}]}

        >>> features = [{'name': 'package', 'version': 'package_name=git_vim', 'provisioner': 'salt'},
        ...             {'name': 'package', 'version': 'package_name=curl', 'provisioner': 'salt'}]
        >>> pprint.pprint(FeaturesProvisionerAnsible(None, None, {}, {}, global_config)._format_provisioner_features(features)[-1])
        {'hosts': 'all', 'name': 'Ghost application features', 'roles': []}

        >>> features = [{'name': 'package', 'version': 'package_name=git_vim'},
        ...             {'name': 'package', 'version': 'package_name=curl'}]
        >>> pprint.pprint(FeaturesProvisionerAnsible(None, None, {}, {}, global_config)._format_provisioner_features(features)[-1])
        {'hosts': 'all', 'name': 'Ghost application features', 'roles': []}

        >>> features = [{'name': 'package', 'version': 'package_name=git_vim', 'provisioner': 'salt'},
        ...             {'name': 'package', 'parameters': {"package_name": ["curl", "vim"]}, 'provisioner': 'ansible'}]
        >>> pprint.pprint(FeaturesProvisionerAnsible(None, None, {}, global_config).format_provisioner_features(features)[-1])
        {'hosts': 'all',
         'name': 'Ghost application features',
         'roles': [{'package_name': ['curl', 'vim'], 'role': 'package'}]}

        """
        with open(self._ansible_base_playbook_file, 'r') as base_playbook:
            playbook = yaml.load(base_playbook)
        playbook.append(copy.deepcopy(ANSIBLE_BASE_PLAYBOOK))
        for ft in features:
            if ft.get('provisioner', self._default_provisioner) != self.name:
                continue
            feature_name = ft['name'].encode('utf-8')
            if ft.get('parameters'):
                role_params = ft.get('parameters') or {}
                role_params['role'] = feature_name
                playbook[-1]['roles'].append(role_params)
            else:
                # Fallback to legacy code with a unique version/value argument
                values = ft.get('version', '').split('=', 1)  # Split only one time
                if len(values) == 2:
                    ft_param_key = values[0].encode('utf-8')
                    ft_param_val = values[1].encode('utf-8')
                    playbook[-1]['roles'].append({'role': feature_name, ft_param_key: ft_param_val})
                else:
                    playbook[-1]['roles'].append({'role': feature_name})
        return playbook

    def format_provisioner_params(self, features):
        return None