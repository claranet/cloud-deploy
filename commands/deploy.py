import os
import sys
import datetime
import calendar
import time
import shutil
import tempfile
from sh import git,bash
from pymongo import MongoClient
from commands.tools import GCallException, gcall, log, find_ec2_instances
from commands.initrepo import InitRepo
from boto.ec2 import autoscale
import boto.s3
import jinja
import base64

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))

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

    def __init__(self, worker):
        self._app = worker.app
        self._job = worker.job
        self._log_file = worker.log_file
        self._config = worker._config
        self._worker = worker
        # FIXME Deal with multiple job modules.
        # Deal only with first (0) job module for now

    def _find_modules_by_name(self, modules):
        for module in modules:
            if 'name' in module:
                for item in self._app['modules']:
                    if 'name' in item and item['name'] == module['name']:
                        yield item

    def _get_path_from_app(self):
        return "/ghost/{name}/{env}/{role}".format(name=self._app['name'], env=self._app['env'], role=self._app['role'])

    def _get_path_from_module(self, module):
        return "/ghost/{name}/{env}/{role}/{module}".format(name=self._app['name'], env=self._app['env'], role=self._app['role'], module=module['name'])

    def _initialize_module(self, module):
        path = self._get_path_from_module(module)
        try:
            shutil.rmtree(path)
        except (OSError, IOError) as e:
            print(e)
        try:
            os.makedirs(path)
        except:
            raise GCallException("Init module: {0} failed, creating directory".format(module['name']))
        os.chdir(path)
        gcall("git clone {git_repo} {path}".format(git_repo=module['git_repo'], path=path), "Git clone", self._log_file)
        self._worker.module_initialized(module['name'])

    def _set_as_conn(self):
        self._as_conn = autoscale.connect_to_region(self._app['region'])

    def _set_autoscale_group(self):
        if not self._as_conn:
            self._set_as_conn()
        if 'autoscale' in self._app.keys():
            if 'name' in self._app['autoscale'].keys():
                self._as_group = self._as_conn.get_all_groups(names=self._app['autoscale']['name'])

    def _start_autoscale(self):
        if not self._as_group:
            self._set_autoscale_group()
        if (self._as_group):
            log("Resuming autoscaling", self._log_file)
            self._as_conn.resume_processes(self._as_group)

    def _stop_autoscale(self):
        if not self._as_group:
            self._set_autoscale_group()
        if (self._as_group):
            log("Stopping autoscaling", self._log_file)
            self._as_conn.suspend_processes(self._as_group)

    def _sync_instances(self, task_name):
        os.chdir(ROOT_PATH)
        hosts = find_ec2_instances(self._app['name'], self._app['env'], self._app['role'], self._app['region'])
        task_name = "deploy:{0}".format(self._config['bucket_s3'])
        if len(hosts) > 0:
            cmd = "/usr/local/bin/fab -i {key_path} set_hosts:ghost_app={app},ghost_env={env},ghost_role={role},region={aws_region},s3_bucket={bucket} {0}".format(task_name, \
                    key_path=self._config['key_path'], app=self._app['name'], env=self._app['env'], role=self._app['role'], aws_region=self._app['region'])
            gcall(cmd, "Updating current instances", self._log_file)
        else:
            log("WARNING: no instance available to sync deployment", self._log_file)

    def _package_module(self, module, ts, commit):
        os.chdir(self._get_path_from_module(module))
        pkg_name = "{0}_{1}_{2}".format(ts, module['name'], commit)
        gcall("tar cvzf ../%s . > /dev/null" % pkg_name, "Creating package: %s" % pkg_name, self._log_file)
        gcall("aws s3 cp ../{0} s3://{bucket_s3}{path}/".format(pkg_name, \
                bucket_s3=self._config['bucket_s3'], path=self._get_path_from_module(module)), "Uploading package: %s" % pkg_name, self._log_file)
        gcall("rm -rf ../{0}".format(pkg_name), "Deleting local package: %s" % pkg_name, self._log_file)
        return pkg_name

    def _purge_old_modules(self, module):
        histories = self._worker._db.deploy_histories.find({'app_id': self._app['_id'], 'module': module['name']}).order({ 'timestamp': -1 }).limit(5)
        if len(histories) > 4:
            to_delete = histories[3]
        task_name = "purge:{0}".format(to_delete)
        gcall("/usr/local/bin/fab -i {key_path} set_hosts:ghost_app={app},ghost_env={env},ghost_role={role},region={aws_region} {0}".format(task_name, **self._app), "Purging package: %s" % pkg_name)

    def _get_module_revision(self, module_name):
        for module in self._job['modules']:
            if 'name' in module and module['name'] == module_name:
                if 'rev' in module:
                    return module['rev']
                return 'master'

    def execute(self):
        try:
            self._apps_modules = self._find_modules_by_name(self._job['modules'])
            for module in self._apps_modules:
                if not module['initialized']:
                    self._initialize_module(module)

            self._apps_modules = self._find_modules_by_name(self._job['modules'])
            for module in self._apps_modules:
                self._execute_deploy(module)

            self._worker.update_status("done", message="Deployment OK")
        except GCallException as e:
            self._worker.update_status("failed", message=str(e))

    def _update_manifest(self, module, package):
        key_path = self._get_path_from_app() + '/MANIFEST'
        conn = boto.s3.connect_to_region(self._app['region'])
        bucket = conn.get_bucket(self._config['bucket_s3'])
        key = bucket.get_key(key_path)
        modules = []
        module_exist = False
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
                        print(tmp)
                        mod['package'] = tmp[1]
                        mod['path'] = tmp[2]
                    modules.append(mod)
        if not key:
            key = bucket.new_key(key_path)
        if not module_exist:
            modules.append({ 'name': module['name'], 'package': package, 'path': module['path']})
        for mod in modules:
            data = data + mod['name'] + ':' + mod['package'] + ':' + mod['path'] + '\n'
        manifest, manifest_path = tempfile.mkstemp()
        if sys.version > '3':
            os.write(manifest, bytes(data, 'UTF-8'))
        else:
            os.write(manifest, data)
        os.close(manifest)
        key.set_contents_from_filename(manifest_path)

    def _execute_deploy(self, module):
        now = datetime.datetime.utcnow()
        ts = calendar.timegm(now.timetuple())
        os.chdir(self._get_path_from_module(module))
        gcall("git clean -f", "Reseting git repository", self._log_file)
        gcall("git pull", "Git pull", self._log_file)
        revision = self._get_module_revision(module['name'])
        gcall("git checkout %s" % revision, "Git checkout: %s" % revision, self._log_file)
        commit = git('rev-parse', '--short', 'HEAD').strip()
        # FIXME execute predeploy
        print('pre deploy')
        # Execute buildpack
        if 'build_pack' in module:
            print('execute buildpack')
            buildpack_source = base64.b64decode(module['build_pack'])
            buildpack, buildpack_path = tempfile.mkstemp()
            if sys.version > '3':
                os.write(buildpack, bytes(buildpack_source, 'UTF-8'))
            else:
                os.write(buildpack, buildpack_source)
            gcall("bash "+buildpack_path,'Buildpack execute' ,self._log_file)
        # Store postdeploy script in tarball
        if 'post_deploy' in module:
            postdeploy_source = base64.b64decode(module['post_deploy'])
            with open(self.get_path_from_module(module) + '/postdeploy', 'w') as f:
                if sys.version > '3':
                    f.write(bytes(postdeploy_source, 'UTF-8'))
                else:
                    f.write(postdeploy_source)
        self._set_as_conn()
        self._stop_autoscale()
        self._update_manifest(module, pkg_name)
        self._sync_instances('deploy')
        self._start_autoscale()
        self._purge_old_modules(module)
        deployment = {'app_id': self._app['_id'], 'job_id': self._job['_id'], 'module': module['name'], 'commit': commit, 'timestamp': ts, 'package': pkg_name}
        self._worker._db.deploy_histories.insert(deployment)

    def finish():
        pass
