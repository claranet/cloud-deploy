import os
import time
import yaml
import json
from ghost_log import log
from pylxd import Client

PROVISIONER_LOCAL_TREE="/tmp/ghost-features-provisioner"

class Lxd:
    def __init__(self, app, job, config, log_file):
        self._app = app
        self._job = job
        self._log_file = log_file
        self._config = config
        self.client = Client()
        self.container_name= "lxd-{env}-{region}-{role}-{name}-{date}".format(env=self._app['env'],
                                                                              region=self._app['region'],
                                                                              role=self._app['role'],
                                                                              name=self._app['name'],
                                                                              date=time.strftime("%Y%m%d-%H%M%S"))
        self._container_config = self._config.get('container', {
                    'endpoint': self._config.get('endpoint', 'localhost'),
                    'debug': self._config.get('debug', 'False'),
            })


    def _create_containers_config(self):
        config = {}
        alias = self._app['build_infos']["source_container_image"]
        if self._job["command"] == u"buildimage":
            alias = self._app['build_infos']["source_container_image"]
            if self._container_config['endpoint'] == "localhost":
                config['source'] = { "type": "image", "alias": alias }
            else:
                config['source'] = {"type": "image", "protocol":"simplestreams", "mode":"pull" ,"alias": alias, "server" : self._container_config['endpoint']}

        elif self._job["command"] == u"deploy":
            alias = self._app['build_infos']["container_image"]
            config['source'] = { "type": "image", "alias": alias }

        config['name'] = self.container_name
        config['ephemeral'] = False
        config['config'] = { "security.privileged": 'True' }
        config['profiles'] = ["default", self.container_name]
        return config

    def _create_containers_profile(self,module=None):
        log("Create container profile ", self._log_file)

        if self._job['command'] == u"buildimage":
            source_formulas = "{base}/salt-{job_id}".format(base=PROVISIONER_LOCAL_TREE, job_id=self._job['_id'])
            source_hooks = "/ghost/{app_name}/{env}/{role}".format(app_name=self._app['name'],env=self._app['env'],role=self._app['role'])
            devices= {'formulas': {'path': '/srv', 'source': source_formulas , 'type': 'disk'}, 'hooks': {'path': '/ghost', 'source': source_hooks , 'type': 'disk'}}


        elif self._job['command'] == u"deploy":
            source_module = "/ghost/{app_name}/{env}/{role}/{module_name}".format(app_name=self._app['name'],env=self._app['env'],role=self._app['role'],module_name=module['name'])
            module_path = module['path']
            devices={'buildpack': {'path': module_path, 'source': source_module , 'type': 'disk'}}

        self.client.profiles.create(self.container_name, devices=devices)


    def _delete_containers_profile(self):
        os.system("lxc profile delete {container_name}".format(container_name=self.container_name))

    def _create_container(self):
        log("Create container {container_name}".format(container_name=self.container_name), self._log_file)
        self.container =  self.client.containers.create(self._create_containers_config(),wait=True)
        self.container.start(wait=True)
        time.sleep(5)

    def _publish_container(self):
        log("Publish Container as image", self._log_file)
        os.system("lxc publish local:{container_name} local: --alias={job_id} description={container_name}".format(job_id=self._job['_id'], container_name=self.container_name))

    def _clean_lxd_images(self):
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
        salt_bootstrap = self.container.execute(["wget", "-O", "bootstrap-salt.sh", "https://bootstrap.saltstack.com"])
        self._container_log(salt_bootstrap)
        salt_bootstrap = self.container.execute(["sh", "bootstrap-salt.sh"])
        self._container_log(salt_bootstrap)

    def _lxd_run_salt_call(self):
        log("run salt features install", self._log_file)
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

    def _build_image(self):
        self._create_containers_profile()
        self._create_container()
        self._lxd_bootstrap()
        self._lxd_run_hooks_pre()
        self._lxd_run_salt_call()
        self._lxd_run_hooks_post()
        self.container.stop(wait=True)
        return self

    def _deploy(self, script_path, module):
        self._create_containers_profile(module)
        self._create_container()
        self._execute_buildpack(script_path,module)
        self.container.stop(wait=True)
        if not self._container_config['debug']:
            self._clean()
        return self
