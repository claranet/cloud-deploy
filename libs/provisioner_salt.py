import yaml
import os

from ghost_log import log

SALT_LOCAL_TREE="/tmp/salt/"

class ProvisionerSalt:
    def __init__(self, log_file, unique_id):
        self._log_file = log_file
        self.unique = unique_id

        if not os.path.exists(SALT_LOCAL_TREE):
            os.makedirs(SALT_LOCAL_TREE)

    def _get_local_tree_path(self):
        if not os.path.exists(SALT_LOCAL_TREE + self.unique):
            os.makedirs(SALT_LOCAL_TREE + self.unique)
        return SALT_LOCAL_TREE + self.unique

    def _build_salt_top(self, params):
        self.salt_path = SALT_LOCAL_TREE + self.unique + '/salt'
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
        self.salt_pillar_path = SALT_LOCAL_TREE + self.unique + '/pillar'
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

