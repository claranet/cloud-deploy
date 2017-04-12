import os
import sys
import time
import yaml
import json
from ghost_log import log
from pylxd import Client as lxd_client
from ghost_tools import get_buildpack_clone_path_from_module, get_path_from_app_with_color, get_local_repo_path

PROVISIONER_LOCAL_TREE="/tmp/ghost-features-provisioner"


class Lxd:
    def __init__(self, app, job, config, log_file):
        self._app = app
        self._job = job
        self._log_file = log_file
        self._config = config
        self.client = lxd_client()
        self._container_name = "lxd-{env}-{region}-{role}-{name}-{job_id}".format(env=self._app['env'],
                                                                              region=self._app['region'],
                                                                              role=self._app['role'],
                                                                              name=self._app['name'],
                                                                              job_id=self._job['_id'])
        self._container_config = self._config.get('container', {'endpoint': self._config.get('endpoint', 'localhost'),
                                                                'debug': self._config.get('debug', 'False'),
                                                               })
        self._provisioners_config = config.get('features_provisioners', {'salt'})
        self.skip_salt_bootstrap_option = self._job['options'][0] if 'options' in self._job and len(self._job['options']) > 0 else True

    def _create_containers_config(self):
        """ Generate a container configuration according build image or deployment
        >>> app = {u'env': u'prod', u'role': u'webfront', u'name': u'AppName', u'region': u'eu-west-1', u'build_infos': { u'container_image': u'58cc276cd4128930c201e52e', u'source_container_image': u'58cc203dd4128930c201e519'}}
        >>> job = {u'command': u'buildimage', u'_id': '58cd0e7dd4128910e0d747ed'}
        >>> log_file = None
        >>> config = {}
        >>> Lxd(app, job, config, log_file)._create_containers_config()
        {'config': {'security.privileged': 'True'}, 'profiles': ['default', 'lxd-prod-eu-west-1-webfront-AppName-58cd0e7dd4128910e0d747ed'], 'name': 'lxd-prod-eu-west-1-webfront-AppName-58cd0e7dd4128910e0d747ed', 'source': {'alias': u'58cc203dd4128930c201e519', 'type': 'image'}, 'ephemeral': False}
        """
        config = {}
        alias = self._app['build_infos']["source_container_image"]
        if self._job["command"] == u"buildimage":
            alias = self._app['build_infos']["source_container_image"]
            if self._container_config['endpoint'] == "localhost":
                config['source'] = { "type": "image", "alias": alias }
            else:
                config['source'] = {"type": "image", "protocol":"simplestreams", "mode":"pull", "alias": alias, "server" : self._container_config['endpoint']}

        elif self._job["command"] == u"deploy":
            alias = self._app['build_infos']["container_image"]
            config['source'] = { "type": "image", "alias": alias }

        config['name'] = self._container_name
        config['ephemeral'] = False
        config['config'] = { "security.privileged": 'True' }
        config['profiles'] = ["default", self._container_name]
        dirname, filename = os.path.split(os.path.abspath(__file__))
        return config

    def _create_containers_profile(self,module=None):
        """ Generate Lxc profile to mount provisoner local tree and ghost application according build image or deployment
        >>> from StringIO import StringIO
        >>> app = {u'env': u'prod', u'role': u'webfront', u'name': u'AppName', u'region': u'eu-west-1'}
        >>> job = {u'command': u'buildimage', u'_id': '58cd0e7dd4128910e0d747db'}
        >>> log_file = StringIO()
        >>> config = {}
        >>> Lxd(app, job, config, log_file)._create_containers_profile()
        """
        log("Create container profile", self._log_file)
        if self._job['command'] == u"buildimage":
            source_formulas = get_local_repo_path(PROVISIONER_LOCAL_TREE, self._app['name'], self._job['_id'])
            source_hooks = get_path_from_app_with_color(self._app)
            devices= {'formulas': {'path': '/srv', 'source': source_formulas , 'type': 'disk'}, 'hooks': {'path': '/ghost', 'source': source_hooks , 'type': 'disk'}}

        elif self._job['command'] == u"deploy":
            source_module = get_buildpack_clone_path_from_module(self._app, module)
            module_path = module['path']
            devices={'buildpack': {'path': module_path, 'source': source_module , 'type': 'disk'}}

        self.client.profiles.create(self._container_name, devices=devices)

    def _create_container(self,module=None, wait=5):
        """ Create a container with his profile and set time paramet to wait until network was up (default: 5 sec)
        >>> from StringIO import StringIO
        >>> app = {u'env': u'prod', u'role': u'webfront', u'name': u'AppName', u'region': u'eu-west-1', u'build_infos': { u'source_container_image': u'debian/jessie'}}
        >>> job = {u'command': u'buildimage', u'_id': '58cd0e7dd4128910e0d747td'}
        >>> log_file = StringIO()
        >>> config = {}
        >>> container = Lxd(app, job, config, log_file)._create_container()
        """
        log("Create container {container_name}".format(container_name=self._container_name), self._log_file)
        self._create_containers_profile(module)
        self.container =  self.client.containers.create(self._create_containers_config(),wait=True)
        self.container.start(wait=True)
        time.sleep(wait)
        return self.container

    def _delete_containers_profile(self):
        """ Delete the container profile
        >>> from StringIO import StringIO
        >>> app = {u'env': u'prod', u'role': u'webfront', u'name': u'AppName', u'region': u'eu-west-1'}
        >>> job = {u'command': u'buildimage', u'_id': '58cd0e7dd4128910e0d747db'}
        >>> log_file = StringIO()
        >>> config = {}
        >>> Lxd(app, job, config, log_file)._delete_containers_profile()
        """
        os.system("lxc profile delete {container_name}".format(container_name=self._container_name))

    def _publish_container(self):
        """ Publish container as image on registry local after build image
        >>> from StringIO import StringIO
        >>> app = {u'env': u'prod', u'role': u'webfront', u'name': u'AppName', u'region': u'eu-west-1'}
        >>> job = {u'command': u'buildimage', u'_id': '58cd0e7dd4128910e0d747td'}
        >>> log_file = StringIO()
        >>> config = {}
        >>> Lxd(app, job, config, log_file)._publish_container()
        """
        log("Publish Container as image", self._log_file)
        os.system("lxc publish local:{container_name} local: --alias={job_id} description={container_name} --force".format(job_id=self._job['_id'], container_name=self._container_name))

    def _clean_lxd_images(self):
        """ Clean lxd image in local registry as aws ami with ami_retention parameter
        >>> from StringIO import StringIO
        >>> app = {u'env': u'prod', u'role': u'webfront', u'name': u'AppName', u'region': u'eu-west-1', u'build_infos': { u'source_container_image': u'debian/jessie'}}
        >>> job = {u'command': u'buildimage', u'_id': '58cd0e7dd4128910e0d747ed'}
        >>> log_file = StringIO()
        >>> config = {}
        >>> Lxd(app, job, config, log_file)._clean_lxd_images()
        """
        log("Cleanup image", self._log_file)
        retention = self._config.get('ami_retention', 5)
        ami_name_format = "lxd-{env}-{region}-{role}-{name}".format(env=self._app['env'], region=self._app['region'], role=self._app['role'], name=self._app['name'])
        filtered_images = []
        images = self.client.images.all()
        for image in images:
            filtered_images.append(image)

        if filtered_images and len(filtered_images) > retention:
            filtered_images.sort(key=lambda img: img.uploaded_at, reverse = True)
            i = 0
            while i < retention:
                filtered_images.pop(0)
                i += 1

            for image in filtered_images:
                image.delete()

    def _lxd_bootstrap(self):
        log("Bootstrap container", self._log_file)
        update = self.container.execute(["apt-get", "--force-yes", "update"])
        self._container_log(update)
        wget = self.container.execute(["apt-get", "-y", "--force-yes", "install", "apt-utils", "wget" , "sudo"])
        self._container_log(wget)
        if 'salt' in self._provisioners_config and self.skip_salt_bootstrap_option:
            salt_bootstrap = self.container.execute(["wget", "-O", "bootstrap-salt.sh", "https://bootstrap.saltstack.com"])
            self._container_log(salt_bootstrap)
            salt_bootstrap = self.container.execute(["sh", "bootstrap-salt.sh"])
            self._container_log(salt_bootstrap)

    def _lxd_run_features_install(self):
        log("run features install", self._log_file)
        if 'salt' in self._provisioners_config:
            salt_call = self.container.execute(["salt-call" , "state.highstate", "--local", "-l", "info"])
            self._container_log(salt_call)

    def _lxd_run_hooks_pre(self):
        log("run build images pre build", self._log_file)
        prehooks = self.container.execute(["sh" , "/ghost/hook-pre_buildimage"])
        self._container_log(prehooks)

    def _lxd_run_hooks_post(self):
        log("run build images post build", self._log_file)
        posthooks = self.container.execute(["sh" , "/ghost/hook-post_buildimage"])
        self._container_log(posthooks)

    def _execute_buildpack(self,script_path,module):
        log("run deploy build pack", self._log_file)
        script = os.path.basename(script_path)
        buildpack = self.container.execute(["sed" , "2icd "+module['path'], "-i" ,"{module_path}/{script}".format(module_path=module['path'],script=script)])
        self._container_log(buildpack)
        buildpack = self.container.execute(["sudo", "-u", "ghost", "sh" , "{module_path}/{script}".format(module_path=module['path'],script=script)])
        self._container_log(buildpack)

    def _container_log(self, cmd):
        if cmd.stdout:
            log(cmd.stdout, self._log_file)
        if cmd.stderr:
            log(cmd.stderr, self._log_file)

    def _clean(self):
        self.container.delete()
        self._delete_containers_profile()

    def build_image(self):
        self._create_container()
        self._lxd_bootstrap()
        self._lxd_run_hooks_pre()
        self._lxd_run_features_install()
        self._lxd_run_hooks_post()
        self.container.stop(wait=True)
        return self

    def deploy(self, script_path, module):
        self._create_container(module)
        self._execute_buildpack(script_path,module)
        self.container.stop(wait=True)
        if not self._container_config['debug']:
            self._clean()
        return self
