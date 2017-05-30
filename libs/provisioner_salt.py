import os
import re
import yaml

from ghost_log import log

from .provisioner import FeaturesProvisioner

class FeaturesProvisionerSalt(FeaturesProvisioner):
    def __init__(self, log_file, unique_id, config, global_config):
        FeaturesProvisioner.__init__(self, log_file, 'salt', unique_id, config, global_config)

    def build_provisioner_features_files(self, params, features):
        self._build_salt_top(features)
        self._build_salt_pillar(params)

    def build_packer_provisioner_config(self, packer_config):
        return {
            'type': 'salt-masterless',
            'local_state_tree': self.local_repo_path + '/salt',
            'local_pillar_roots': self.local_repo_path + '/pillar',
            'skip_bootstrap': packer_config['skip_salt_bootstrap'],
        }

    def build_packer_provisioner_cleanup(self):
        return {
            'type': 'shell',
            'inline': [
                "sudo rm -rf /srv/salt || echo 'salt: no cleanup salt'",
                "sudo rm -rf /srv/pillar || echo 'salt: no cleanup pillar'"
            ]
        }

    def _build_salt_top(self, params):
        self.salt_path = self.local_repo_path + '/salt'
        self.salt_top_path = self.salt_path + '/top.sls'
        stream = file(self.salt_top_path, 'w')
        log("Writing Salt Top state to: {0}".format(self.salt_top_path), self._log_file)
        #The common sls file is optional
        if os.path.exists(self.salt_path + '/common'):
            data = {'base': {'*': ['common'] + params }}
        else:
            data = {'base': {'*': params }}
        log('state: top.sls: {0}'.format(data), self._log_file)
        yaml.dump(data, stream, default_flow_style=False)

    def _build_salt_pillar(self, features):
        self.salt_pillar_path = self.local_repo_path + '/pillar'
        self.salt_pillar_top_path = self.salt_pillar_path + '/top.sls'
        self.salt_pillar_features_path = self.salt_pillar_path + '/features.sls'
        #Creating top.sls to call features.sls
        stream_top = file(self.salt_pillar_top_path, 'w')
        data_top = {'base': {'*': ['features']}}
        log('pillar: top.sls: {0}'.format(data_top), self._log_file)
        yaml.dump(data_top, stream_top, default_flow_style=False)
        #Creating features.sls file based on ghost app features
        stream_features = file(self.salt_pillar_features_path, 'w')
        log('pillar: features.sls: {0}'.format(features), self._log_file)
        yaml.dump(features, stream_features, default_flow_style=False)

    def format_provisioner_features(self, features):
        """ Generates the formula dictionnary object with all required features

        >>> features = [{'name': 'pkg', 'version': 'git_vim'}, {'name': 'pkg', 'version': 'package=lsof'}, {'name': 'pkg', 'version': 'package=curl'}]
        >>> FeaturesProvisionerSalt(None, None, None, None).format_provisioner_features(features)
        ['pkg']

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
        >>> pprint.pprint(FeaturesProvisionerSalt(None, None, None, None).format_provisioner_params(features).items())
        [('pkg', {'package': ['lsof', 'curl'], 'version': 'git_vim'})]

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
