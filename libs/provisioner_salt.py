import yaml
import os

from ghost_log import log
from .provisioner import FeaturesProvisioner

class FeaturesProvisionerSalt(FeaturesProvisioner):
    def __init__(self, log_file, unique_id, config, global_config):
        FeaturesProvisioner.__init__(self, 'salt', log_file, unique_id, config, global_config)

    def build_provisioner_features_files(self, params, features):
        self._build_salt_top(params)
        self._build_salt_pillar(features)

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
