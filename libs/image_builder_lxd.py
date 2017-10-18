# -*- coding: utf-8 -*-

import os
import time

from pylxd import Client as LXDClient

from ghost_log import log
from ghost_tools import gcall, GCallException, get_provisioners_config, boolify
from libs.deploy import get_buildpack_clone_path_from_module, get_local_repo_path, get_path_from_app_with_color
from .image_builder import ImageBuilder

PROVISIONER_LOCAL_TREE = "/tmp/ghost-features-provisioner"


class LXDImageBuilder(ImageBuilder):
    """
    This class is designed to Build an lxc container using lxd
    """

    def __init__(self, app, job, db, log_file, config):
        ImageBuilder.__init__(self, app, job, db, log_file, config)

        self._client = LXDClient()
        self._container_name = self._ami_name.replace('.', '-')
        self._container_config = self._config.get('container', {
            'endpoint': self._config.get('endpoint', 'localhost'),
            'debug': self._config.get('debug', False),
        })
        provisioners_config = get_provisioners_config()
        self.provisioners = []
        for key, provisioner_config in provisioners_config.iteritems():
            if key == 'salt':
                self.provisioners.append('salt')
            elif key == 'ansible':
                self.provisioners.append('ansible')
            else:
                log("Invalid provisioner type. Please check your yaml 'config.yml' file", self._log_file)
                raise GCallException("Invalid features provisioner type")
        self.skip_salt_bootstrap_option = self._job['options'][0] if 'options' in self._job and len(
            self._job['options']) > 0 else True

    def _create_containers_config(self):
        """ Generate a container configuration according build image or deployment
        """
        config = {}
        if self._job["command"] == u"buildimage":
            fingerprint = self._app['build_infos']["source_container_image"]
            if self._container_config['endpoint'] == "localhost":
                config['source'] = {"type": "image", "fingerprint": fingerprint}
            else:
                config['source'] = {
                    "type": "image",
                    "protocol": "lxd",
                    "mode": "pull",
                    "fingerprint": fingerprint,
                    "server": self._container_config['endpoint']
                }
        elif self._job["command"] == u"deploy":
            alias = self._app['build_infos']["container_image"]
            config['source'] = {"type": "image", "alias": alias}
        else:
            raise Exception("Incompatible command given to LXD Builder")

        config['name'] = self._container_name
        config['ephemeral'] = False
        config['config'] = {"security.privileged": 'True'}
        config['profiles'] = ["default", self._container_name]
        log("Generated LXC container config {}".format(config), self._log_file)
        return config

    def _create_containers_profile(self, module=None):
        """ Generate Lxc profile to mount provisoner local tree and ghost application according build image or deployment
        """
        log("Creating container profile", self._log_file)
        if self._job['command'] == u"buildimage":
            devices = {}
            '''
                TO DO
            '''
            if 'salt' in self.provisioners:
                source_formulas = get_local_repo_path(PROVISIONER_LOCAL_TREE, 'salt', self._job['_id'])
                devices['salt'] = {'path': '/srv', 'source': source_formulas, 'type': 'disk'}
            if 'ansible' in self.provisioners:
                source_formulas = get_local_repo_path(PROVISIONER_LOCAL_TREE, 'ansible', self._job['_id'])
                devices['ansible'] = {'path': '/srv/', 'source': source_formulas, 'type': 'disk'}

            source_hooks = get_path_from_app_with_color(self._app)
            devices['hooks'] = {'path': '/ghost', 'source': source_hooks, 'type': 'disk'}

        elif self._job['command'] == u"deploy":
            source_module = get_buildpack_clone_path_from_module(self._app, module)
            module_path = module['path']
            devices = {'buildpack': {'path': module_path, 'source': source_module, 'type': 'disk'}}

        profile = self._client.profiles.create(self._container_name, devices=devices)
        log("Created container profile: {}".format(profile.name), self._log_file)

    def _create_container(self, module=None, wait=10):
        """ Create a container with his profile and set time paramet to wait until network was up (default: 5 sec)
        """
        log("Create container {container_name}".format(container_name=self._container_name), self._log_file)
        self._create_containers_profile(module)
        self.container = self._client.containers.create(self._create_containers_config(), wait=True)
        log("Created container, starting it")
        self.container.start(wait=True)
        time.sleep(wait)
        return self.container

    def _delete_containers_profile(self):
        """ Delete the container profile
        """
        gcall("lxc profile delete {container_name}".format(container_name=self._container_name),
              "Delete container profile", self._log_file)

    def _publish_container(self):
        """ Publish container as image on registry local after build image
        """
        self._clean_lxd_images()
        gcall("lxc publish {container_name} local: --alias={job_id} description={container_name} --force".format(
            job_id=self._job['_id'], container_name=self._container_name), "Publish Container as image", self._log_file)

    def _clean_lxd_images(self):
        """ Clean lxd image in local registry as aws ami with ami_retention parameter
        """
        log("Cleanup image", self._log_file)
        retention = self._config.get('ami_retention', 5)
        filtered_images = []
        images = self._client.images.all()
        for image in images:
            filtered_images.append(image)

        if filtered_images and len(filtered_images) > retention:
            filtered_images.sort(key=lambda img: img.uploaded_at, reverse=True)
            i = 0
            while i < retention:
                filtered_images.pop(0)
                i += 1

            for image in filtered_images:
                image.delete()

    def _set_ghost_env_vars(self):
        for var in self._format_ghost_env_vars():
            self.container.execute(["export", var])
        for var in self._app.get('env_vars', []):
            self.container.execute(["export", var])

    def _lxd_bootstrap(self):
        log("Bootstrap container", self._log_file)
        self._set_ghost_env_vars()
        if not boolify(self.skip_salt_bootstrap_option):
            if 'salt' in self.provisioners:
                salt_bootstrap = self.container.execute(
                    ["wget", "-O", "bootstrap-salt.sh", "https://bootstrap.saltstack.com"])
                self._container_log(salt_bootstrap)
                self._container_execution_error(salt_bootstrap, "Salt bootstrap")
                salt_bootstrap = self.container.execute(["sh", "bootstrap-salt.sh"])
                self._container_log(salt_bootstrap)
                self._container_execution_error(salt_bootstrap, "Salt bootstrap")
            if 'ansible' in self.provisioners:
                ansible_bootstrap = self.container.execute(["pip", "install", "--yes", "ansible"])
                self._container_log(ansible_bootstrap)
                self._container_execution_error(ansible_bootstrap, "Ansible bootstrap")

    def _lxd_run_features_install(self):
        log("Run features install", self._log_file)
        if 'salt' in self.provisioners:
            salt_call = self.container.execute(["salt-call", "state.highstate", "--local", "-l", "info"])
            self._container_log(salt_call)
            self._container_execution_error(salt_call, "salt execution")

        if 'ansible' in self.provisioners:
            run_playbooks = self.container.execute(["ansible-playbook", "/srv/main.yml"])
            self._container_log(run_playbooks)
            self._container_execution_error(run_playbooks, "ansible execution")

    def _lxd_run_hooks_pre(self):
        log("Run build images pre build", self._log_file)
        prehooks = self.container.execute(["sh", "/ghost/hook-pre_buildimage"])
        self._container_log(prehooks)
        self._container_execution_error(prehooks, "pre hooks")

    def _lxd_run_hooks_post(self):
        log("Run build images post build", self._log_file)
        posthooks = self.container.execute(["sh", "/ghost/hook-post_buildimage"])
        self._container_log(posthooks)
        self._container_execution_error(posthooks, "post hooks")

    def _execute_buildpack(self, script_path, module):
        log("Run deploy build pack", self._log_file)
        script = os.path.basename(script_path)
        self.container.execute(["sed", "2icd " + module['path'], "-i",
                                "{module_path}/{script}".format(module_path=module['path'], script=script)])
        buildpack = self.container.execute(["sh", "{module_path}/{script}".format(module_path=module['path'],
                                                                                  script=script)])
        self._container_log(buildpack)
        self.container.execute(["chown", "-R", "1001:1002", "{module_path}".format(module_path=module['path'])])
        self._container_execution_error(buildpack, "buildpack")
        return buildpack.exit_code

    @staticmethod
    def _container_execution_error(logs, step):
        if logs.exit_code != 0:
            raise Exception(False, step)

    def _container_log(self, cmd):
        if cmd.stdout:
            log(cmd.stdout.encode('utf-8'), self._log_file)
        if cmd.stderr:
            log(cmd.stderr.encode('utf-8'), self._log_file)

    def _clean(self):
        self.container.delete(wait=True)
        self._delete_containers_profile()

    def start_builder(self):
        try:
            self._create_container()
            self._lxd_bootstrap()
            self._lxd_run_hooks_pre()
            self._lxd_run_features_install()
            self._lxd_run_hooks_post()
        except Exception as msg:
            raise msg
        finally:
            self.container.stop(wait=True)
            self._publish_container()
            if not self._container_config['debug']:
                self._clean()

    def purge_old_images(self):
        raise NotImplementedError

    def deploy(self, script_path, module):
        self._create_container(module)
        buildpack_status = self._execute_buildpack(script_path, module)
        self.container.stop(wait=True)
        if not self._container_config['debug']:
            self._clean()
        return buildpack_status
