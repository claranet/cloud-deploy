import json
import re
import time


from pypacker import Packer
from ghost_log import log
from ghost_aws import create_launch_config, generate_userdata, check_autoscale_exists, purge_launch_configuration, update_auto_scale
from settings import cloud_connections, DEFAULT_PROVIDER
from ghost_tools import get_aws_connection_data

COMMAND_DESCRIPTION = "Update the autoscaling group and its LaunchConfiguration"

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
        self._connection_data = get_aws_connection_data(
                self._app.get('assumed_account_id', ''),
                self._app.get('assumed_role_name', ''),
                self._app.get('assumed_region_name', '')
                )
        self._cloud_connection = cloud_connections.get(self._app.get('provider', DEFAULT_PROVIDER))(
                self._log_file,
                **self._connection_data
                )

    def execute(self):
        log("Updating AutoScaling", self._log_file)
        ami_id = self._app['ami']
        if ami_id:
            if self._app['autoscale']['name']:
                if check_autoscale_exists(self._cloud_connection, self._app['autoscale']['name'], self._app['region']):
                    userdata = None
                    launch_config = None
                    userdata = generate_userdata(self._config['bucket_s3'], self._config.get('bucket_region', self._app['region']), self._config['ghost_root_path'])
                    if userdata:
                        launch_config = create_launch_config(self._cloud_connection, self._app, userdata, ami_id)
                        log("Launch configuration [{0}] created.".format(launch_config.name), self._log_file)
                        if launch_config:
                            update_auto_scale(self._cloud_connection, self._app, launch_config, self._log_file, update_as_params=True)
                            if (purge_launch_configuration(self._app, self._config.get('launch_configuration_retention', 5))):
                                log("Old launch configurations removed for this app", self._log_file)
                            else:
                                log("ERROR: Purge launch configurations failed", self._log_file)
                            self._worker.update_status("done")
                        else:
                            log("ERROR: Cannot update autoscaling group", self._log_file)
                            self._worker.update_status("failed")
                    else:
                        log("ERROR: Cannot generate userdata. The bootstrap.sh file can maybe not be found.", self._log_file)
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
