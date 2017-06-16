import os
import yaml
from fabric.colors import yellow as _yellow, red as _red

from ghost_log import log
from ghost_tools import gcall, GCallException, boolify, config
from .provisioner import FeaturesProvisioner, GalaxyNoMatchRoles

class FeaturesProvisionerAnsible(FeaturesProvisioner):
    """ Build features with ansible """
    def __init__(self, log_file, unique_id, config, global_config):
        FeaturesProvisioner.__init__(self, log_file, 'ansible', unique_id, config, global_config)
        self._ansible_playbook_path = self.local_repo_path + '/main.yml'
        self._ansible_galaxy_role_path = self.local_repo_path + '/roles'
        self._ansible_requirement_app = self.local_repo_path + '/requirement_app.yml'
        self._ansible_command = "ANSIBLE_FORCE_COLOR=1 PYTHONUNBUFFERED=1 sudo ansible-playbook"
        self._ansible_base_playbook = [{'hosts': 'localhost', 'roles':[]}]

    def build_provisioner_features_files(self, params, features):
        self._enabled_packer_ansible_config = self._test_not_empty_ansible_features(features)
        if self._enabled_packer_ansible_config:
            self._build_ansible_galaxy_requirement(features)
            self._build_ansible_playbook(features)

    def _build_ansible_playbook(self, features):
        """ Write ansible playbook from application features """
        with open(self._ansible_playbook_path, "w") as stream_features:
            log("Ansible - Writing playbook: {0}".format(self._ansible_playbook_path), self._log_file)
            log(_yellow("Ansible - features: {0}".format(features[0]['roles'])), self._log_file)
            try:
                yaml.dump(features, stream_features, default_flow_style=False, explicit_start=True)
            except yaml.YAMLError, exc:
                log(_red("Ansible - ERROR Writing playbook: {0}".format(exc)), self._log_file)
                raise

    def _test_not_empty_ansible_features(self, features):
        """ Test is features set

        >>> features = [{'hosts': 'localhost', 'roles': []}]
        >>> import pprint
        >>> pprint.pprint(FeaturesProvisionerAnsible(None, None, None, None)._test_not_empty_ansible_features(features))
        False

        >>> features = [{'hosts': 'localhost', 'roles': [{'role': 'package', 'package_name': ['git_vim']}]}]      
        >>> pprint.pprint(FeaturesProvisionerAnsible(None, None, None, None)._test_not_empty_ansible_features(features))
        True

        """
        return features != [{'hosts': 'localhost', 'roles': []}]

    def _get_ansible_roles(self, features):
        """ Get role list with unique role

        >>> features = [{'hosts': 'localhost', 'roles': [{'role': 'package', 'package_name': ['git_vim']}, {'role': 'package', 'package_name': ['curl']}, {'role': 'apache2', 'hostname': 'localhost'}]}]
        >>> import pprint
        >>> pprint.pprint(sorted(FeaturesProvisionerAnsible(None, None, None, None)._get_ansible_roles(features)))
        ['apache2', 'package']

        >>> features = [{'hosts': 'localhost', 'roles': []}]
        >>> pprint.pprint(sorted(FeaturesProvisionerAnsible(None, None, None, None)._get_ansible_roles(features)))
        []

        """
        return list(set([r['role'] for r in features[0]['roles']]))

    def _get_roles_from_requirement(self, role):
        """ Return only galaxy roles (yaml document) needed from application """
        self._ansible_galaxy_rq_path = self.local_repo_path + '/' + self.config.get('ansible_galaxy_requirements_path', 'requirements.yml')
        if os.path.exists(self._ansible_galaxy_rq_path):
            with open(self._ansible_galaxy_rq_path, 'r') as stream_requirement:
                requirements_yaml = yaml.load_all(stream_requirement)
                for requirement in requirements_yaml:
                    for feature in requirement:
                        if feature['name'] == role:
                            return feature
        else:
            log(_red("Ansible - ERROR path doesn't exist : {0}".format(self._ansible_galaxy_rq_path)), self._log_file)

    def _build_ansible_galaxy_requirement(self, features):
        """ Generates ansible galaxy requirement file from features """
        requirement_app = []
        for role in self._get_ansible_roles(features):
            requirement_app.append(self._get_roles_from_requirement(role))
        if requirement_app != [None]:
            with open(self._ansible_requirement_app, "w") as stream_requirement_app:
                yaml.dump(requirement_app, stream_requirement_app, default_flow_style=False)
            log("Ansible - Getting roles from : {0}".format(self._ansible_galaxy_rq_path), self._log_file)
            try:
                gcall('ansible-galaxy install -r %s -p %s' % (self._ansible_requirement_app, self._ansible_galaxy_role_path), 'Ansible -  ansible-galaxy command failed', self._log_file)
            except GCallException:
                raise
        else:
            raise GalaxyNoMatchRoles("Ansible - ERROR: No roles match galaxy requirements for one or more features {0}".format(features[0]['roles']))

    def build_packer_provisioner_config(self, packer_config):
        self._ansible_bootstrap_path = str(config['ghost_root_path']) + '/scripts/ansible_bootstrap.sh'
        if os.path.exists(self._ansible_bootstrap_path):
            if not boolify(packer_config.get('skip_provisioner_bootstrap', 'True')):
                if self._enabled_packer_ansible_config:
                    return [{
                        'type': 'shell',
                        'script': self._ansible_bootstrap_path,
                        'execute_command' : "chmod +x {{ .Path }}; sudo bash -c '{{ .Vars }} {{ .Path }}'"
                    }, {
                        'type': 'ansible-local',
                        'playbook_dir': self.local_repo_path,
                        'playbook_file': self.local_repo_path + '/main.yml',
                        'command': self._ansible_command
                    }]
            else:
                if self._enabled_packer_ansible_config:
                    return [{
                        'type': 'ansible-local',
                        'playbook_dir': self.local_repo_path,
                        'playbook_file': self.local_repo_path + '/main.yml',
                        'command': self._ansible_command
                    }]

    def build_packer_provisioner_cleanup(self):
        return None

    def format_provisioner_features(self, features):
        """ Generates the role dictionnary object with all required features and their options

        >>> features = [{'name': 'package', 'version': 'package_name=git_vim', 'provisioner': 'ansible'}, {'name': 'package', 'version': 'package_name=curl', 'provisioner': 'ansible'}]
        >>> import pprint
        >>> pprint.pprint(sorted(FeaturesProvisionerAnsible(None, None, None, None).format_provisioner_features(features)))
        [{'hosts': 'localhost',
          'roles': [{'package_name': 'git_vim', 'role': 'package'},
                    {'package_name': 'curl', 'role': 'package'}]}]

        >>> features = [{'name': 'package', 'version': 'package_name=git_vim', 'provisioner': 'salt'}, {'name': 'package', 'version': 'package_name=curl', 'provisioner': 'ansible'}]
        >>> pprint.pprint(sorted(FeaturesProvisionerAnsible(None, None, None, None).format_provisioner_features(features)))
        [{'hosts': 'localhost',
          'roles': [{'package_name': 'curl', 'role': 'package'}]}]

        >>> features = [{'name': 'package', 'version': 'package_name=git_vim', 'provisioner': 'salt'}, {'name': 'package', 'version': 'package_name=curl', 'provisioner': 'salt'}]
        >>> pprint.pprint(sorted(FeaturesProvisionerAnsible(None, None, None, None).format_provisioner_features(features)))
        [{'hosts': 'localhost', 'roles': []}]

        >>> features = [{'name': 'package', 'version': 'package_name=git_vim'}, {'name': 'package', 'version': 'package_name=curl'}]
        >>> pprint.pprint(sorted(FeaturesProvisionerAnsible(None, None, None, None).format_provisioner_features(features)))
        [{'hosts': 'localhost', 'roles': []}]

        """
        playbook = self._ansible_base_playbook
        for ft in features:
            if ft.get('provisioner', self._default_provisioner) != self.name:
                continue
            values = ft.get('version', '').split('=', 1) # Split only one time
            feature_name = ft['name'].encode('utf-8')
            if len(values) == 2:
                ft_param_key = values[0].encode('utf-8')
                ft_param_val = values[1].encode('utf-8')
                playbook[0]['roles'].append({'role': feature_name, ft_param_key: ft_param_val})
            else:
                playbook[0]['roles'].append({'role': feature_name})
        return playbook

    def format_provisioner_params(self, features):
        return None
