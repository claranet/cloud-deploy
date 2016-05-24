import base64
import calendar
import datetime
import io
import os
import sys
from sh import git
import tempfile
from time import sleep

import boto.s3

from ghost_tools import GCallException, gcall, deploy_module_on_hosts, log, refresh_stage2, get_app_module_name_list, clean_local_module_workspace

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))

COMMAND_DESCRIPTION = "Deploy a module"

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
        # FIXME Deal with multiple job modules.
        # Deal only with first (0) job module for now

    def _find_modules_by_name(self, modules):
        result = []
        for module in modules:
            if 'name' in module:
                for item in self._app['modules']:
                    if 'name' in item and item['name'] == module['name']:
                        result.append(item)
        return result

    def _get_path_from_app(self):
        """
        >>> class worker:
        ...     app = {'name': 'AppName', 'env': 'prod', 'role': 'webfront'}
        ...     job = None
        ...     log_file = None
        ...     _config = None
        >>> Deploy(worker=worker())._get_path_from_app()
        '/ghost/AppName/prod/webfront'
        """
        return "/ghost/{name}/{env}/{role}".format(name=self._app['name'], env=self._app['env'], role=self._app['role'])

    def _get_mirror_path_from_module(self, module):
        """
        >>> class worker:
        ...     app = None
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
        clone_path = self._get_buildpack_clone_path_from_module(module)
        return '{}/.tmp{}'.format(clone_path[:6], clone_path[6:])

    def _get_buildpack_clone_path_from_module(self, module):
        """
        >>> class worker:
        ...     app = {'name': 'AppName', 'env': 'prod', 'role': 'webfront'}
        ...     job = None
        ...     log_file = None
        ...     _config = None
        >>> module = {'name': 'mod1', 'git_repo': 'git@bitbucket.org:morea/ghost.git'}
        >>> Deploy(worker=worker())._get_buildpack_clone_path_from_module(module)
        '/ghost/AppName/prod/webfront/mod1'
        """
        return "{app_path}/{module}".format(app_path=self._get_path_from_app(), module=module['name'])


    def _deploy_module(self, module, fabric_execution_strategy):
        deploy_module_on_hosts(module, fabric_execution_strategy, self._app, self._config, self._log_file)

    def _package_module(self, module, ts, commit):
        path = self._get_buildpack_clone_path_from_module(module)
        os.chdir(path)
        pkg_name = "{0}_{1}_{2}".format(ts, module['name'], commit)
        pkg_path = '../{0}'.format(pkg_name)
        uid = module.get('uid', os.geteuid())
        gid = module.get('gid', os.getegid())
        gcall("tar czf {0} --owner={1} --group={2} .".format(pkg_path, uid, gid), "Creating package: %s" % pkg_name, self._log_file)

        log("Uploading package: %s" % pkg_name, self._log_file)
        conn = boto.s3.connect_to_region(self._config.get('bucket_region', self._app['region']))
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
                if 'rev' in module:
                    return module['rev']
                return 'master'

    def _get_notification_message_done(self, deploy_ids):
        """
        >>> from bson.objectid import ObjectId
        >>> class worker:
        ...   app = None
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
        ...   app = None
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
        ...   app = None
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

        self._apps_modules = self._find_modules_by_name(self._job['modules'])
        if not self._apps_modules:
            self._worker.update_status("aborted", message=self._get_notification_message_aborted(self._job['modules']))
            return

        refresh_stage2(self._config.get('bucket_region', self._app['region']), self._config)
        module_list = []
        for module in self._apps_modules:
            if 'name' in module:
                module_list.append(module['name'])
        split_comma = ', '
        module_list = split_comma.join(module_list)
        try:
            deploy_ids = {}
            for module in self._apps_modules:
                deploy_id = self._execute_deploy(module, fabric_execution_strategy)
                deploy_ids[module['name']] = deploy_id
                self._worker._db.jobs.update({ '_id': self._job['_id'], 'modules.name': module['name']}, {'$set': {'modules.$.deploy_id': deploy_id }})
                self._worker._db.apps.update({ '_id': self._app['_id'], 'modules.name': module['name']}, {'$set': { 'modules.$.initialized': True }})

            self._worker.update_status("done", message=self._get_notification_message_done(deploy_ids))
        except GCallException as e:
            self._worker.update_status("failed", message=self._get_notification_message_failed(module_list, e))

    def _update_manifest(self, module, package):
        key_path = self._get_path_from_app() + '/MANIFEST'
        conn = boto.s3.connect_to_region(self._config.get('bucket_region', self._app['region']))
        bucket = conn.get_bucket(self._config['bucket_s3'])
        key = bucket.get_key(key_path)
        modules = []
        module_exist = False
        all_app_modules_list = get_app_module_name_list(self._app['modules'])
        data = ""
        if key:
            manifest = key.get_contents_as_string()
            if sys.version > '3':
                manifest = manifest.decode('utf-8')
            for line in manifest.split('\n'):
                if line:
                    mod = {}
                    tmp = line.split(':')
                    mod['name'] = tmp[0]
                    if mod['name'] == module['name']:
                        mod['package'] = package
                        mod['path'] = module['path']
                        module_exist = True
                    else:
                        mod['package'] = tmp[1]
                        mod['path'] = tmp[2]
                    # Only keep modules that have not been removed from the app
                    if mod['name'] in all_app_modules_list:
                        mod['index'] = all_app_modules_list.index(mod['name'])
                        modules.append(mod)
        if not key:
            key = bucket.new_key(key_path)
        if not module_exist:
            modules.append({
                'name': module['name'],
                'package': package,
                'path': module['path'],
                'index': all_app_modules_list.index(module['name'])
            })
        for mod in sorted(modules, key=lambda mod: mod['index']):
            data = data + mod['name'] + ':' + mod['package'] + ':' + mod['path'] + '\n'
        manifest, manifest_path = tempfile.mkstemp()
        if sys.version > '3':
            os.write(manifest, bytes(data, 'UTF-8'))
        else:
            os.write(manifest, data)
        os.close(manifest)
        key.set_contents_from_filename(manifest_path)
        os.remove(manifest_path)

    def _is_commit_hash(self, revision):
        """
        Returns True is revision is a valid commit hash, False otherwise.

        ***NOTE***:
        This test invokes git rev-parse in the current working directory and will fail
        if commit 8f6c4dba19559319a6a898d093f3f3aaa09cd6e9 is not in the history.

        >>> class worker:
        ...   app = None
        ...   job = None
        ...   log_file = None
        ...   _config = None

        >>> Deploy(worker=worker())._is_commit_hash('HEAD')
        False

        >>> Deploy(worker=worker())._is_commit_hash('master')
        False

        >>> Deploy(worker=worker())._is_commit_hash('dev')
        False

        >>> Deploy(worker=worker())._is_commit_hash('8f6c4dba19559319a6a898d093f3f3aaa09cd6e9')
        True

        A valid abbreviated hash must be at least 4 characters long:

        >>> Deploy(worker=worker())._is_commit_hash('8f6c')
        True

        Shorter substrings won't match:

        >>> Deploy(worker=worker())._is_commit_hash('8f6')
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

    def _execute_deploy(self, module, fabric_execution_strategy):
        """
        Returns the deployment id
        """

        now = datetime.datetime.utcnow()
        ts = calendar.timegm(now.timetuple())

        git_repo = module['git_repo']
        mirror_path = self._get_mirror_path_from_module(module)
        clone_path = self._get_buildpack_clone_path_from_module(module)
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
            predeploy_source = base64.b64decode(module['pre_deploy'])
            with open(clone_path + '/predeploy', 'w') as f:
                if sys.version > '3':
                    f.write(bytes(predeploy_source, 'UTF-8'))
                else:
                    f.write(predeploy_source)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)

        # Execute buildpack
        if 'build_pack' in module:
            buildpack_source = base64.b64decode(module['build_pack'])
            buildpack, buildpack_path = tempfile.mkstemp(dir=clone_path)
            if sys.version > '3':
                os.write(buildpack, bytes(buildpack_source, 'UTF-8'))
            else:
                os.write(buildpack, buildpack_source)
            os.close(buildpack)

            buildpack_env = os.environ.copy()
            buildpack_env['GHOST_APP'] = self._app['name']
            buildpack_env['GHOST_ENV'] = self._app['env']
            buildpack_env['GHOST_ROLE'] = self._app['role']
            buildpack_env['GHOST_MODULE_NAME'] = module['name']
            buildpack_env['GHOST_MODULE_PATH'] = module['path']

            gcall('bash %s' % buildpack_path, 'Buildpack: Execute', self._log_file, env=buildpack_env)
            gcall('du -hs .', 'Display current build directory disk usage', self._log_file)
            gcall('rm -vf %s' % buildpack_path, 'Buildpack: Done, cleaning temporary file', self._log_file)

        # Store postdeploy script in tarball
        if 'post_deploy' in module:
            log("Create post_deploy script for inclusion in target package", self._log_file)
            postdeploy_source = base64.b64decode(module['post_deploy'])
            with open(clone_path + '/postdeploy', 'w') as f:
                if sys.version > '3':
                    f.write(bytes(postdeploy_source, 'UTF-8'))
                else:
                    f.write(postdeploy_source)
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

        self._update_manifest(module, pkg_name)
        all_app_modules_list = get_app_module_name_list(self._app['modules'])
        clean_local_module_workspace(self._get_path_from_app(), all_app_modules_list, self._log_file)
        self._deploy_module(module, fabric_execution_strategy)

        deployment = {'app_id': self._app['_id'], 'job_id': self._job['_id'], 'module': module['name'], 'revision': revision, 'commit': commit, 'commit_message': commit_message, 'timestamp': ts, 'package': pkg_name, 'module_path': module['path']}
        return self._worker._db.deploy_histories.insert(deployment)
