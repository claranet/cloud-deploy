import os

PROVISIONER_LOCAL_TREE="/tmp/ghost-features-provisioner"

class FeaturesProvisioner:
    def __init__(self, log_file, unique_id, type, config):
        self._log_file = log_file
        self.unique = unique_id
        self.type = type
        self.config = config

        if not os.path.exists(PROVISIONER_LOCAL_TREE):
            os.makedirs(PROVISIONER_LOCAL_TREE)

        self.local_tree_path = self._get_local_tree_path()
        if not os.path.exists(self.local_tree_path):
            os.makedirs(self.local_tree_path)

    def _get_local_tree_path(self):
        return "{base}/{type}-{uid}".format(base=PROVISIONER_LOCAL_TREE, type=self.type, uid=self.unique)

    def build_provisioner_features_files(self, params, features):
        raise NotImplementedError

    def build_packer_provisioner_config(self, packer_config):
        raise NotImplementedError

    def build_packer_provisioner_cleanup(self):
        raise NotImplementedError
