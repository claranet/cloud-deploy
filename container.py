import os
import time
import yaml
import json
from ghost_log import log
from pylxd import Client

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

    def _create_containers_config(self):
        config = {}
        if self._job["command"] == u"buildimage":
            alias = self._app['build_infos']['container']
            if self._config.get('container_endpoint','localhost') == "localhost":
                config['source'] = { "type": "image", "alias": alias }
            else:
                config['source'] = {"type": "image", "protocol":"simplestreams", "mode":"pull" ,"alias": alias, "server" : self._config.get('container_endpoint','https://images.linuxcontainers.org')}

        elif self._job["command"] == u"deploy":
            alias = self._app['build_infos']["container"]

        config['name'] = self.container_name
        config['ephemeral'] = False
        config['config'] = { "security.privileged": 'True' }
        config['profiles'] = ["default", self.container_name]
        return config

    def _create_containers_profile(self,module=None):
        log("Create container profile ", self._log_file)

        if self._job['command'] == u"buildimage":
            source_formulas = "/tmp/salt/{job_id}".format(job_id=self._job['_id'])
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
        log("Start Container", self._log_file)
        update = self.container.execute(["apt-get", "--force-yes", "update"])
        log(update.stdout, self._log_file)
        wget = self.container.execute(["apt-get", "-y", "--force-yes", "install", "apt-utils", "wget" , "sudo"])
        log(wget.stdout, self._log_file)
        salt_boostrap = self.container.execute(["wget", "-O", "bootstrap-salt.sh", "https://bootstrap.saltstack.com"])
        salt_boostrap = self.container.execute(["sh", "bootstrap-salt.sh"])
        log(salt_boostrap.stdout, self._log_file)

    def _lxd_run_salt_call(self):
        log("run salt features install", self._log_file)
        salt_call = self.container.execute(["salt-call" , "state.highstate", "--local", "-l", "info"])
        log(salt_call.stdout, self._log_file)

    def _lxd_run_hooks_pre(self):
        log("run build images pre build", self._log_file)
        prehooks = self.container.execute(["sh" , "/ghost/hook-pre_buildimage"])
        log(prehooks.stdout, self._log_file)

    def _lxd_run_hooks_post(self):
        log("run build images post build", self._log_file)
        posthooks = self.container.execute(["sh" , "/ghost/hook-post_buildimage"])
        log(posthooks.stdout, self._log_file)

    def _execute_buildpack(self,script_path,module):
        log("run deploy build pack", self._log_file)
        script = os.path.basename(script_path)
        buildpack = self.container.execute(["sed" , "2icd "+module['path'], "-i" ,"{module_path}/{script}".format(module_path=module['path'],script=script)])
        buildpack = self.container.execute(["sudo", "-u", "ghost", "sh" , "{module_path}/{script}".format(module_path=module['path'],script=script)])
        log(buildpack.stderr, self._log_file)
        log(buildpack.stdout, self._log_file)

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
        if not self._config.get('container_debug','False'):
            self._clean()
        return self
