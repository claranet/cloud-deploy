import yaml
import os

from ghost_log import log
from .provisioner import FeaturesProvisioner

class FeaturesProvisionerAnsible(FeaturesProvisioner):
    def __init__(self, log_file, unique_id, config, global_config):
        FeaturesProvisioner.__init__(self, log_file, 'ansible', unique_id, config, global_config)

    def build_provisioner_features_files(self, params, features):
        raise NotImplementedError

    def build_packer_provisioner_config(self, packer_config):
        return {
            'type': 'ansible-local',
            'playbook_dir': self.local_tree_path,
            'playbook_file': self.local_tree_path + '/main.yml'
        }

    def build_packer_provisioner_cleanup(self):
        raise NotImplementedError
