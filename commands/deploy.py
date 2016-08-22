import calendar
import datetime
import io
import os
import sys
from sh import git
import tempfile
from time import sleep

from ghost_tools import b64decode_utf8
from ghost_tools import GCallException, gcall, get_app_module_name_list, clean_local_module_workspace, refresh_stage2
from ghost_tools import get_aws_connection_data
from ghost_log import log
from ghost_aws import deploy_module_on_hosts
from settings import cloud_connections, DEFAULT_PROVIDER
from libs.deploy import execute_module_script_on_ghost
from libs.deploy import get_path_from_app_with_color, get_buildpack_clone_path_from_module, update_app_manifest

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))

COMMAND_DESCRIPTION = "Deploy module(s)"

class Deploy():
    _app = None
    _job = None
    _log_file = -1
    _app_path = None
    _git_repo = None
    _dry_run = None
    _as_conn = None
    _as_group = None
    _worker = None
    _config = None

    def __init__(self, worker):
        self._app = worker.app
        self._job = worker.job
        self._log_file = worker.log_file
        self._config = worker._config
        self._worker = worker
        self._connection_data = get_aws_connection_data(
                self._app.get('assumed_account_id', ''),
                self._app.get('assumed_role_name', ''),
                self._app.get('assumed_region_name', '')
                )
        self._cloud_connection = cloud_connections.get(self._app.get('provider', DEFAULT_PROVIDER))(
                self._log_file,
                **self._connection_data
                )

    def _find_modules_by_name(self, modules):
        result = []
        for module in modules:
            if 'name' in module:
                for item in self._app['modules']:
                    if 'name' in item and item['name'] == module['name']:
                        result.append(item)
        return result

    def _get_mirror_path_from_module(self, module):
        """
        >>> class worker:
        ...     app = {}
        ...     job = None
        ...     log_file = None
        ...     _config = None
        >>> module = {'git_repo': 'git@bitbucket.org:morea/ghost.git'}
        >>> Deploy(worker=worker())._get_mirror_path_from_module(module)
        '/ghost/.mirrors/git@bitbucket.org:morea/ghost.git'
        """
        return "/ghost/.mirrors/{remote}".format(remote=module['git_repo'])

    def _get_intermediate_clone_path_from_module(self, module):
        """
        >>> class worker:
        ...     app = {'name': 'AppName', 'env': 'prod', 'role': 'webfront'}
        ...     job = None
        ...     log_file = None
        ...     _config = None
        >>> module = {'name': 'mod1', 'git_repo': 'git@bitbucket.org:morea/ghost.git'}
        >>> Deploy(worker=worker())._get_intermediate_clone_path_from_module(module)
        '/ghost/.tmp/AppName/prod/webfront/mod1'
        """
        clone_path = get_buildpack_clone_path_from_module(self._app, module)
        return '{}/.tmp{}'.format(clone_path[:6], clone_path[6:])

    def _deploy_module(self, module, fabric_execution_strategy, safe_deployment_strategy):
        deploy_module_on_hosts(self._cloud_connection, module, fabric_execution_strategy, self._app, self._config, self._log_file, safe_deployment_strategy)

    def _package_module(self, module, ts, commit):
        path = get_buildpack_clone_path_from_module(self._app, module)
        os.chdir(path)
        pkg_name = "{0}_{1}_{2}".format(ts, module['name'], commit)
        pkg_path = '../{0}'.format(pkg_name)
        uid = module.get('uid', os.geteuid())
        gid = module.get('gid', os.getegid())
        gcall("tar czf {0} --owner={1} --group={2} .".format(pkg_path, uid, gid), "Creating package: %s" % pkg_name, self._log_file)

        log("Uploading package: %s" % pkg_name, self._log_file)
        cloud_connection = cloud_connections.get(self._app.get('provider', DEFAULT_PROVIDER))(self._log_file)
        conn = cloud_connection.get_connection(self._config.get('bucket_region', self._app['region']), ["s3"])
        bucket = conn.get_bucket(self._config['bucket_s3'])
        key_path = '{path}/{pkg_name}'.format(bucket_s3=self._config['bucket_s3'], path=path, pkg_name=pkg_name)
        key = bucket.get_key(path)
        if not key:
            key = bucket.new_key(key_path)
        key.set_contents_from_filename(pkg_path)

        gcall("rm -f {0}".format(pkg_path), "Deleting local package: %s" % pkg_name, self._log_file)
        return pkg_name

    def _get_module_revision(self, module_name):
        for module in self._job['modules']:
            if 'name' in module and module['name'] == module_name:
                if 'rev' in module and module['rev']:
                    return module['rev']
                return 'HEAD'

    def _get_notification_message_done(self, deploy_ids):
        """
        >>> from bson.objectid import ObjectId
        >>> class worker:
        ...   app = {}
        ...   job = None
        ...   log_file = None
        ...   _config = None
        >>> Deploy(worker=worker())._get_notification_message_done({})
        'Deployment OK: []'
        >>> Deploy(worker=worker())._get_notification_message_done({'mod1': ObjectId('012345678901234567890123')})
        'Deployment OK: [mod1: 012345678901234567890123]'
        >>> Deploy(worker=worker())._get_notification_message_done({'mod1': ObjectId('012345678901234567890123'), 'mod2': ObjectId('987654321098765432109876')})
        'Deployment OK: [mod1: 012345678901234567890123, mod2: 987654321098765432109876]'
        """
        message = ', '.join([': '.join((key, str(value))) for key, value in sorted(deploy_ids.items())])
        return 'Deployment OK: [{0}]'.format(message)

    def _get_notification_message_failed(self, module_list, e):
        """
        >>> class worker:
        ...   app = {}
        ...   job = None
        ...   log_file = None
        ...   _config = None
        >>> Deploy(worker=worker())._get_notification_message_failed('', 'Exception')
        'Deployment Failed: [] Exception'
        >>> Deploy(worker=worker())._get_notification_message_failed('mod1', 'Exception')
        'Deployment Failed: [mod1] Exception'
        >>> Deploy(worker=worker())._get_notification_message_failed('mod1, mod2', 'Exception')
        'Deployment Failed: [mod1, mod2] Exception'
        """
        return "Deployment Failed: [{0}] {1}".format(module_list, str(e))

    def _get_notification_message_aborted(self, modules):
        """
        >>> class worker:
        ...   app = {}
        ...   job = None
        ...   log_file = None
        ...   _config = None
        >>> Deploy(worker=worker())._get_notification_message_aborted([])
        'Deployment Aborted: missing modules []'
        >>> Deploy(worker=worker())._get_notification_message_aborted([{'name': 'mod1'}])
        'Deployment Aborted: missing modules [mod1]'
        >>> Deploy(worker=worker())._get_notification_message_aborted([{'name': 'mod1'}, {'name': 'mod2'}])
        'Deployment Aborted: missing modules [mod1, mod2]'
        """
        message = ', '.join([module['name'] for module in modules])
        return "Deployment Aborted: missing modules [{0}]".format(message)

    def execute(self):
        fabric_execution_strategy = self._job['options'][0] if 'options' in self._job and len(self._job['options']) > 0 else None
        safe_deployment_strategy = self._job['options'][1] if 'options' in self._job and len(self._job['options']) > 1 else None

        self._apps_modules = self._find_modules_by_name(self._job['modules'])
        if not self._apps_modules:
            self._worker.update_status("aborted", message=self._get_notification_message_aborted(self._job['modules']))
            return

        refresh_stage2(cloud_connections.get(self._app.get('provider', DEFAULT_PROVIDER))(self._log_file),
                self._config.get('bucket_region', self._app['region']), self._config
                )
        module_list = []
        for module in self._apps_modules:
            if 'name' in module:
                module_list.append(module['name'])
        split_comma = ', '
        module_list = split_comma.join(module_list)
        try:
            deploy_ids = {}
            for module in self._apps_modules:
                deploy_id = self._execute_deploy(module, fabric_execution_strategy, safe_deployment_strategy)
                deploy_ids[module['name']] = deploy_id
                self._worker._db.jobs.update({ '_id': self._job['_id'], 'modules.name': module['name']}, {'$set': {'modules.$.deploy_id': deploy_id }})
                self._worker._db.apps.update({ '_id': self._app['_id'], 'modules.name': module['name']}, {'$set': { 'modules.$.initialized': True }})

            self._worker.update_status("done", message=self._get_notification_message_done(deploy_ids))
        except GCallException as e:
            self._worker.update_status("failed", message=self._get_notification_message_failed(module_list, e))

    def _is_commit_hash(self, revision):
        """
        Returns True is revision is a valid commit hash, False otherwise.

        ***NOTE***:
        This test invokes git rev-parse in the current working directory and will fail
        if git is not installed or run outside of a git workspace.

        >>> class worker:
        ...   app = {}
        ...   job = None
        ...   log_file = None
        ...   _config = None

        >>> Deploy(worker=worker())._is_commit_hash('HEAD')
        False

        >>> Deploy(worker=worker())._is_commit_hash('master')
        False

        >>> Deploy(worker=worker())._is_commit_hash('dev')
        False

        >>> current_git_hash = git('--no-pager', 'rev-parse', 'HEAD', _tty_out=False).strip()
        >>> Deploy(worker=worker())._is_commit_hash(current_git_hash)
        True

        A valid abbreviated hash must be at least 4 characters long:

        >>> Deploy(worker=worker())._is_commit_hash(current_git_hash[:4])
        True

        Shorter substrings won't match:

        >>> Deploy(worker=worker())._is_commit_hash(current_git_hash[:3])
        False
        """

        resolved_revision = ''
        try:
            # git rev-parse returns a complete hash from an abbreviated hash, if valid
            resolved_revision = git('--no-pager', 'rev-parse', revision, _tty_out=False).strip()
        except:
            pass

        # If resolved_revision begins with or equals revision, it is a commit hash
        return resolved_revision.find(revision) == 0

    def _execute_deploy(self, module, fabric_execution_strategy, safe_deployment_strategy):
        """
        Returns the deployment id
        """

        now = datetime.datetime.utcnow()
        ts = calendar.timegm(now.timetuple())

        git_repo = module['git_repo']
        mirror_path = self._get_mirror_path_from_module(module)
        clone_path = get_buildpack_clone_path_from_module(self._app, module)
        revision = self._get_module_revision(module['name'])

        if not os.path.exists(mirror_path):
            gcall('git --no-pager clone --bare --mirror {r} {m}'.format(r=git_repo, m=mirror_path),
                  'Create local git mirror for remote {r}'.format(r=git_repo),
                  self._log_file)

        # If an index.lock file exists in the mirror, wait until it disappears before trying to update the mirror
        while os.path.exists('{m}/index.lock'.format(m=mirror_path)):
            log('The git mirror is locked by another process, waiting 5s...', self._log_file)
            sleep(5000)

        # Update existing git mirror
        os.chdir(mirror_path)
        gcall('git --no-pager remote update',
              'Update local git mirror from remote {r}'.format(r=git_repo),
              self._log_file)

        # Resolve HEAD symbolic reference to identify the default branch
        head = git('--no-pager', 'symbolic-ref', '--short', 'HEAD', _tty_out=False).strip()

        # If revision is HEAD, replace it by the default branch
        if revision == 'HEAD':
            revision = head

        # If revision is a commit hash, a full intermediate clone is required before getting a shallow clone
        if self._is_commit_hash(revision):
            # Create intermediate clone from the local git mirror, chdir into it and fetch all commits
            source_path = self._get_intermediate_clone_path_from_module(module)
            gcall('rm -rf {p}'.format(p=source_path), 'Removing previous intermediate clone', self._log_file)
            os.makedirs(source_path)
            os.chdir(source_path)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)
            gcall('git --no-pager init', 'Git init intermediate clone', self._log_file)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)
            gcall('git --no-pager remote add origin file://{m}'.format(m=mirror_path), 'Git add local mirror as origin for intermediate clone', self._log_file)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)
            gcall('git --no-pager fetch origin', 'Git fetch all commits from origin', self._log_file)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)
            gcall('git --no-pager checkout {r}'.format(r=revision), 'Git checkout revision into intermediate clone: {r}'.format(r=revision), self._log_file)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)

            # Create shallow clone from the intermediate clone, chdir into it and retrieve submodules
            gcall('rm -rf {p}'.format(p=clone_path), 'Removing previous clone', self._log_file)
            os.makedirs(clone_path)
            os.chdir(clone_path)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)
            gcall('git --no-pager clone file://{s} .'.format(s=source_path), 'Git clone from intermediate clone', self._log_file)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)
            gcall('git --no-pager submodule update --init --recursive', 'Git update submodules', self._log_file)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)

            # Destroy intermediate clone
            gcall('rm -rf {p}'.format(p=source_path), 'Removing intermediate clone', self._log_file)
        else:
            # Create clone from the local git mirror, chdir into it, fetch requested revision and retrieve submodules
            gcall('rm -rf {p}'.format(p=clone_path), 'Removing previous clone', self._log_file)
            os.makedirs(clone_path)
            os.chdir(clone_path)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)
            gcall('git --no-pager clone --depth=10 file://{m} -b {r} .'.format(m=mirror_path, r=revision), 'Git clone from local mirror with depth limited to 10 from a specific revision: {r}'.format(r=revision), self._log_file)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)
            gcall('git --no-pager submodule update --init --recursive', 'Git update submodules', self._log_file)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)

        # Extract commit information
        commit = git('--no-pager', 'rev-parse', '--short', 'HEAD', _tty_out=False).strip()
        commit_message = git('--no-pager', 'log', '--max-count=1', '--format=%s', 'HEAD', _tty_out=False).strip()

        # At last, reset remote origin URL
        gcall('git --no-pager remote set-url origin {r}'.format(r=git_repo), 'Git reset remote origin to {r}'.format(r=git_repo), self._log_file)

        # Store predeploy script in tarball
        if 'pre_deploy' in module:
            log("Create pre_deploy script for inclusion in target package", self._log_file)
            predeploy_source = b64decode_utf8(module['pre_deploy'])
            with io.open(clone_path + '/predeploy', mode='w', encoding='utf-8') as f:
                f.write(predeploy_source)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)

        # Execute buildpack
        execute_module_script_on_ghost(self._app, module, 'build_pack', 'Buildpack', clone_path, self._log_file)

        # Store postdeploy script in tarball
        if 'post_deploy' in module:
            log("Create post_deploy script for inclusion in target package", self._log_file)
            postdeploy_source = b64decode_utf8(module['post_deploy'])
            with io.open(clone_path + '/postdeploy', mode='w', encoding='utf-8') as f:
                f.write(postdeploy_source)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)

        # Store after_all_deploy script in tarball
        if 'after_all_deploy' in module:
            log("Create after_all_deploy script for inclusion in target package", self._log_file)
            afteralldeploy_source = b64decode_utf8(module['after_all_deploy'])
            with io.open(clone_path + '/after_all_deploy', mode='w', encoding='utf-8') as f:
                f.write(afteralldeploy_source)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)

        # Store module metadata in tarball
        log("Create metadata file for inclusion in target package", self._log_file)
        module_metadata = u"""
#!/bin/bash

GHOST_MODULE_REPO="{repo}"
GHOST_MODULE_REV="{rev}"
GHOST_MODULE_COMMIT="{commit}"
GHOST_MODULE_COMMIT_MESSAGE="{commitmsg}"
GHOST_MODULE_USER="{user}"

"""
        metavars = {
            "repo": module['git_repo'],
            "rev": revision,
            "commit": commit,
            "commitmsg": commit_message,
            "user": self._job['user']
        }
        module_metadata = module_metadata.format(**metavars)
        with io.open(clone_path + '/.ghost-metadata', mode='w', encoding='utf-8') as f:
            f.write(module_metadata)
        gcall('du -hs .', 'Display current build directory disk usage', self._log_file)

        # Create tar archive
        pkg_name = self._package_module(module, ts, commit)

        update_app_manifest(self._app, self._config, module, pkg_name, self._log_file)
        all_app_modules_list = get_app_module_name_list(self._app['modules'])
        clean_local_module_workspace(get_path_from_app_with_color(self._app), all_app_modules_list, self._log_file)
        self._deploy_module(module, fabric_execution_strategy, safe_deployment_strategy)
        if 'after_all_deploy' in module:
            log("After all deploy script found for '{0}'. Executing it.".format(module['name']), self._log_file)
            execute_module_script_on_ghost(self._app, module, 'after_all_deploy', 'After all deploy', clone_path, self._log_file)

        deployment = {'app_id': self._app['_id'], 'job_id': self._job['_id'], 'module': module['name'], 'revision': revision, 'commit': commit, 'commit_message': commit_message, 'timestamp': ts, 'package': pkg_name, 'module_path': module['path']}
        return self._worker._db.deploy_histories.insert(deployment)
