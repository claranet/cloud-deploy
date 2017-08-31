import os
import copy
import re
import yaml
from fabric.colors import yellow as _yellow

from ghost_log import log

from .provisioner import FeaturesProvisioner

SALT_PILLAR_TOP = {'base': {'*': ['features']}}

class FeaturesProvisionerSalt(FeaturesProvisioner):
    def __init__(self, log_file, unique_id, config, global_config):
        FeaturesProvisioner.__init__(self, log_file, 'salt', unique_id, config, global_config)
        self._salt_state_tree = os.path.join(self.local_repo_path, 'salt')
        self._salt_pillar_roots = os.path.join(self.local_repo_path, 'pillar')
        self._provisioner_log_level = self.global_config.get('provisioner_log_level', 'info')
        self._salt_state_top_path = os.path.join(self._salt_state_tree, 'top.sls')
        self._salt_pillar_top_path = os.path.join(self._salt_pillar_roots, 'top.sls')
        self._salt_pillar_features_path = os.path.join(self._salt_pillar_roots, 'features.sls')
        self._salt_additional_pillar = self.global_config.get('salt_additional_pillar', '')

    def build_provisioner_features_files(self, params, features):
        """ Build salt files only if features with salt provisioner """
        self._enabled_packer_salt_config = self._test_not_empty_salt_features(features)
        if self._enabled_packer_salt_config:
            self._build_salt_top(features)
            self._build_salt_pillar(params)

    def build_packer_provisioner_config(self, packer_config):
        if self._enabled_packer_salt_config:
            return [{
                'type': 'salt-masterless',
                'local_state_tree': self._salt_state_tree,
                'local_pillar_roots': self._salt_pillar_roots,
                'skip_bootstrap': packer_config['skip_provisioner_bootstrap'],
                'log_level': self._provisioner_log_level,
            }]
        else:
            return None

    def build_packer_provisioner_cleanup(self):
        if self._enabled_packer_salt_config:
            return {
                'type': 'shell',
                'inline': [
                    "sudo rm -rf /srv/salt || echo 'Salt - no cleanup salt'",
                    "sudo rm -rf /srv/pillar || echo 'Salt - no cleanup pillar'"
                ]
            }
        else:
            return None

    def _test_not_empty_salt_features(self, features):
        """ Test is features set

        >>> features = []
        >>> import pprint
        >>> pprint.pprint(FeaturesProvisionerSalt(None, None, {}, {})._test_not_empty_salt_features(features))
        False

        >>> features = ['pkg']
        >>> pprint.pprint(FeaturesProvisionerSalt(None, None, {}, {})._test_not_empty_salt_features(features))
        True

        """
        return features != []

    def _build_salt_top(self, params):
        """ Build salt salt/top.sls file from features """
        with open(self._salt_state_top_path, "w") as stream:
            log("Salt - Writing Top state to: {0}".format(self._salt_state_top_path), self._log_file)
            if os.path.exists(os.path.join(self._salt_state_tree, 'common')):
                data = {'base': {'*': ['common'] + params}}
            else:
                data = {'base': {'*': params}}
            log('Salt - state: top.sls: {0}'.format(data), self._log_file)
            yaml.dump(data, stream, default_flow_style=False)

    def _build_salt_pillar(self, features):
        """ Build salt pillar/top.sls and pillar/features.sls """
        data_top = copy.deepcopy(SALT_PILLAR_TOP)
        with open(self._salt_pillar_top_path, "w") as stream_top:
            if self._salt_additional_pillar != '':
                data_top['base']['*'].append(self._salt_additional_pillar)
            else:
                log('Salt - No additional pillar to add', self._log_file)
            log('Salt - pillar: top.sls: {0}'.format(data_top), self._log_file)
            yaml.dump(data_top, stream_top, default_flow_style=False)
        with open(self._salt_pillar_features_path, "w") as stream_features:
            log(_yellow('Salt - pillar: features.sls: {0}'.format(features)), self._log_file)
            yaml.dump(features, stream_features, default_flow_style=False)

    def format_provisioner_features(self, features):
        """ Generates the formula dictionnary object with all required features

        >>> features = [{'name': 'pkg', 'version': 'git_vim'}, {'name': 'pkg', 'version': 'package=lsof'}, {'name': 'pkg', 'version': 'package=curl'}]
        >>> FeaturesProvisionerSalt(None, None, {}, {}).format_provisioner_features(features)
        ['pkg']

        >>> features = [{'name': 'pkg', 'version': 'git_vim', 'provisioner': 'salt'}, {'name': 'pkg', 'version': 'package=lsof', 'provisioner': 'salt'}, {'name': 'pkg', 'version': 'package=curl', 'provisioner': 'salt'}]
        >>> FeaturesProvisionerSalt(None, None, {}, {}).format_provisioner_features(features)
        ['pkg']

        >>> features = []
        >>> FeaturesProvisionerSalt(None, None, {}, {}).format_provisioner_features(features)
        []

        """
        top = []
        for i in features:
            if i.get('provisioner', self._default_provisioner) != self.name:
                continue
            if re.search('^(php|php5)-(.*)', i['name']):
                continue
            if re.search('^zabbix-(.*)', i['name']):
                continue
            if re.search('^gem-(.*)', i['name']):
                continue
            if not i['name'].encode('utf-8') in top:
                top.append(i['name'].encode('utf-8'))
        return top

    def format_provisioner_params(self, features):
        """ Generates the pillar dictionnary object with all required features and their options

        >>> features = [{'name': 'pkg', 'version': 'git_vim'}, {'name': 'pkg', 'version': 'package=lsof'}, {'name': 'pkg', 'version': 'package=curl'}]
        >>> import pprint
        >>> pprint.pprint(FeaturesProvisionerSalt(None, None, {}, {}).format_provisioner_params(features).items())
        [('pkg', {'package': ['lsof', 'curl'], 'version': 'git_vim'})]

        >>> features = [{'name': 'pkg', 'version': 'git_vim', 'provisioner': 'salt'}, {'name': 'pkg', 'version': 'package=lsof', 'provisioner': 'salt'}, {'name': 'pkg', 'version': 'package=curl', 'provisioner': 'salt'}]
        >>> pprint.pprint(FeaturesProvisionerSalt(None, None, {}, {}).format_provisioner_params(features).items())
        [('pkg', {'package': ['lsof', 'curl'], 'version': 'git_vim'})]

        >>> features = [{'name': 'pkg', 'version': 'git_vim', 'provisioner': 'ansible'}, {'name': 'pkg', 'version': 'package=lsof', 'provisioner': 'salt'}, {'name': 'pkg', 'version': 'package=curl', 'provisioner': 'salt'}]
        >>> pprint.pprint(FeaturesProvisionerSalt(None, None, {}, {}).format_provisioner_params(features).items())
        [('pkg', {'package': ['lsof', 'curl']})]

        >>> features = [{'name': 'pkg', 'version': 'git_vim', 'provisioner': 'ansible'}, {'name': 'pkg', 'version': 'package=lsof', 'provisioner': 'ansible'}, {'name': 'pkg', 'version': 'package=curl', 'provisioner': 'ansible'}]
        >>> pprint.pprint(FeaturesProvisionerSalt(None, None, {}, {}).format_provisioner_params(features).items())
        []

        >>> features = []
        >>> pprint.pprint(FeaturesProvisionerSalt(None, None, {}, {}).format_provisioner_params(features).items())
        []

        """
        pillar = {}
        for ft in features:
            if ft.get('provisioner', self._default_provisioner) != self.name:
                continue
            values = ft.get('version', '').split('=', 1) # Split only one time
            feature_name = ft['name'].encode('utf-8')
            if not feature_name in pillar:
                pillar[feature_name] = {}
            if len(values) == 2:
                ft_param_key = values[0].encode('utf-8')
                ft_param_val = values[1].encode('utf-8')
                if not ft_param_key in pillar[feature_name]:
                    pillar[feature_name][ft_param_key] = []
                pillar[feature_name][ft_param_key].append(ft_param_val)
            else:
                pillar[feature_name]['version'] = ft.get('version', '').encode('utf-8')
        return pillar
