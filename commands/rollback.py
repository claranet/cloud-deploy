import time
import json
import os
import sys
import tempfile
import boto.s3
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson.objectid import ObjectId
from commands.tools import GCallException, gcall, log, find_ec2_instances

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))

class Rollback():
    _app = None
    _job = None
    _log_file = -1
    _config = None

    def __init__(self, worker):
        self._app = worker.app
        self._job = worker.job
        self._db = worker._db
        self._worker = worker
        self._config = worker._config
        self._log_file = worker.log_file

    def _find_modules_by_name(self, modules):
        result = []
        for module in modules:
            if 'name' in module:
                for item in self._app['modules']:
                    if 'name' in item and item['name'] == module['name']:
                        result.append(item)
        return result

    def _get_path_from_app(self):
        return "/ghost/{name}/{env}/{role}".format(name=self._app['name'], env=self._app['env'], role=self._app['role'])

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

    def _get_deploy_infos(self, deploy_id):
        deploy_infos = self._db.deploy_histories.find_one({'_id': ObjectId(deploy_id)})
        if deploy_infos:
            module = {}
            module['path'] = deploy_infos['module_path']
            module['name'] = deploy_infos['module']
            return module, deploy_infos['package']
        return None, None

    def _deploy_module(self, module):
        os.chdir(ROOT_PATH)
        hosts = find_ec2_instances(self._app['name'], self._app['env'], self._app['role'], self._app['region'])
        task_name = "deploy:{0},{1}".format(self._config['bucket_s3'], module['name'])
        if len(hosts) > 0:
            cmd = "/usr/local/bin/fab -i {key_path} set_hosts:ghost_app={app},ghost_env={env},ghost_role={role},region={aws_region} {0}".format(task_name, \
                    key_path=self._config['key_path'], app=self._app['name'], env=self._app['env'], role=self._app['role'], aws_region=self._app['region'])
            gcall(cmd, "Updating current instances", self._log_file)
        else:
            log("WARNING: no instance available to sync deployment", self._log_file)

    def _execute_rollback(self, deploy_id):
        module, package = self._get_deploy_infos(deploy_id)
        if module and package:
            self._update_manifest(module, package)
            self._deploy_module(module)
        else:
            raise GCallException("Rollback on deployment ID: {0} failed".format(deploy_id))

    def execute(self):
        log("Rollbacking module", self._log_file)
        if 'options' in self._job:
            if len(self._job['options']) > 0:
                deploy_id = self._job['options'][0]
                try:
                    self._execute_rollback(deploy_id)
                    self._worker.update_status("done", message="Rollback OK: [{0}]".format(module_list))
                except GCallException as e:
                    self._worker.update_status("failed", message="Rollback Failed: [{0}]\n{1}".format(module_list, str(e)))
                finally:
                    return
        self._worker.update_status("failed", message="Incorrect job request: missing options field with deploy_id")

