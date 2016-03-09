import json
import re
import time

import boto.ec2.autoscale

from pypacker import Packer
from ghost_tools import log, create_launch_config, generate_userdata, check_autoscale_exists, purge_launch_configuration

class Updateautoscaling():
    _app = None
    _job = None
    _log_file = -1

    def __init__(self, worker):
        self._app = worker.app
        self._job = worker.job
        self._db = worker._db
        self._worker = worker
        self._config = worker._config
        self._log_file = worker.log_file

    def execute(self):
        log("Updating AutoScaling", self._log_file)
        ami_id = self._app['ami']
        if ami_id:
            if self._app['autoscale']['name']:
                if check_autoscale_exists(self._app['autoscale']['name'], self._app['region']):
                    userdata = None
                    launch_config = None
                    userdata = generate_userdata(self._config['bucket_s3'], self._config.get('bucket_region', self._app['region']), self._config['ghost_root_path'])
                    if userdata:
                        launch_config = create_launch_config(self._app, userdata, ami_id)
                        log("Launch configuration [{0}] created.".format(launch_config.name), self._log_file)
                    else:
                        log("ERROR: Cannot generate userdata. The bootstrap.sh file can maybe not be found.", self._log_file)
                        self._worker.update_status("failed")
                    if launch_config:
                        conn = boto.ec2.autoscale.connect_to_region(self._app['region'])
                        as_group = conn.get_all_groups(names=[self._app['autoscale']['name']])[0]
                        setattr(as_group, 'launch_config_name', launch_config.name)
                        setattr(as_group, 'desired_capacity', self._app['autoscale']['current'])
                        setattr(as_group, 'min_size', self._app['autoscale']['min'])
                        setattr(as_group, 'max_size', self._app['autoscale']['max'])
                        as_group.update()
                        log("Autoscaling group [{0}] updated.".format(self._app['autoscale']['name']), self._log_file)
                        if (purge_launch_configuration(self._app)):
                            log("Old launch configurations removed for this app", self._log_file)
                        else:
                            log("Purge launch configurations failed", self._log_file)
                        self._worker.update_status("done")
                    else:
                        log("ERROR: Cannot update autoscaling group", self._log_file)
                        self._worker.update_status("failed")
                else:
                    log("ERROR: Autoscaling group [{0}] does not exist".format(self._app['autoscale']['name']), self._log_file)
                    self._worker.update_status("failed")
            else:
                log("No autoscaling group name was set", self._log_file)
                self._worker.update_status("done")
        else:
            log("ERROR: ami_id not found. You must use the `buildimage` command first.", self._log_file)
            self._worker.update_status("failed")
