import os
import sh
from sh import git

from ghost_log import log
from ghost_tools import get_lock_path_from_repo
from libs.git_helper import git_remap_submodule, git_acquire_lock, git_release_lock

PROVISIONER_LOCAL_TREE="/tmp/ghost-features-provisioner"
PROVISIONER_LOCAL_MIRROR="/ghost/.mirrors"
ZABBIX_REPO="git@bitbucket.org:morea/zabbix.git"
DEFAULT_PROVISIONER_TYPE="salt"


class GalaxyNoMatchingRolesException(Exception):
    pass


class GalaxyBadRequirementPathException(Exception):
    pass


class FeaturesProvisioner:
    def __init__(self, log_file, name, unique_id, config, global_config):
        self._log_file = log_file
        self.name = name
        self.unique = unique_id
        self.config = config
        self.global_config = global_config

        self._default_provisioner = DEFAULT_PROVISIONER_TYPE

        if not os.path.exists(PROVISIONER_LOCAL_TREE):
            os.makedirs(PROVISIONER_LOCAL_TREE)

        self.local_repo_path = self._get_local_repo_path()
        if not os.path.exists(self.local_repo_path):
            os.makedirs(self.local_repo_path)

        if config:
            self._get_provisioner_repo()

    def _get_local_repo_path(self):
        return "{base}/{name}-{uid}".format(base=PROVISIONER_LOCAL_TREE, name=self.name, uid=self.unique)

    def _get_provisioner_repo(self):
        # Use the configured git repository, if any
        provisioner_git_repo = self.config.get('git_repo')
        provisioner_git_revision = self.config.get('git_revision')

        git_local_mirror = self._get_mirror_path(provisioner_git_repo)
        zabbix_repo = self.global_config.get('zabbix_repo', ZABBIX_REPO)
        lock_path = get_lock_path_from_repo(provisioner_git_repo)
        log("Getting provisioner features from {r}".format(r=provisioner_git_repo), self._log_file)
        try:
            output=git("ls-remote", "--exit-code", provisioner_git_repo, provisioner_git_revision).strip()
            log("Provisioner repository checked successfuly with output: " + output, self._log_file)
        except sh.ErrorReturnCode as e:
            log("Invalid provisioner repository or invalid credentials. Please check your yaml 'config.yml' file", self._log_file)
            raise

        try:
            git_acquire_lock(lock_path, self._log_file)

            # Creates the Provisioner local mirror
            if not os.path.exists(git_local_mirror):
                log("Creating local mirror [{r}] for the first time".format(r=git_local_mirror), self._log_file)
                os.makedirs(git_local_mirror)
                os.chdir(git_local_mirror)
                git.init(['--bare'])
                git.remote(['add', self.name, provisioner_git_repo])
                git.remote(['add', 'zabbix', zabbix_repo])

            log("Fetching local mirror [{r}] remotes".format(r=git_local_mirror), self._log_file)
            os.chdir(git_local_mirror)
            git.fetch(['--all'])
        finally:
            git_release_lock(lock_path, self._log_file)

        log("Cloning [{r}] repo with local mirror reference".format(r=provisioner_git_repo), self._log_file)
        git.clone(['--reference', git_local_mirror, provisioner_git_repo, '-b', provisioner_git_revision, '--single-branch', self.local_repo_path + '/'])
        if os.path.exists(self.local_repo_path + '/.gitmodules'):
            os.chdir(self.local_repo_path)
            log("Re-map submodules on local git mirror", self._log_file)
            git_remap_submodule(self.local_repo_path, zabbix_repo, git_local_mirror, self._log_file)
            log("Submodule init and update", self._log_file)
            git.submodule('init')
            git.submodule('update')

    def _get_mirror_path(self, git_remote):
        """
        Return the local mirror path
        """
        return "{base_mirror}/{remote}".format(base_mirror=PROVISIONER_LOCAL_MIRROR, remote=git_remote.replace('@', '_').replace(':', '_'))

    def build_provisioner_features_files(self, params, features):
        raise NotImplementedError

    def build_packer_provisioner_config(self, packer_config):
        raise NotImplementedError

    def build_packer_provisioner_cleanup(self):
        raise NotImplementedError

    def format_provisioner_features(self, features):
        raise NotImplementedError

    def format_provisioner_params(self, features):
        raise NotImplementedError
