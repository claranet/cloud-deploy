import traceback

from ghost_log import log
from ghost_aws import create_userdata_launchconfig_update_asg
from settings import cloud_connections, DEFAULT_PROVIDER
from ghost_tools import get_aws_connection_data

COMMAND_DESCRIPTION = "Update the autoscaling group and its LaunchConfiguration"
RELATED_APP_FIELDS = ['autoscale', 'environment_infos']


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
                try:
                    if create_userdata_launchconfig_update_asg(ami_id, self._cloud_connection, self._app, self._config, self._log_file, update_as_params=True):
                        self._worker.update_status("done")
                    else:
                        self._worker.update_status("failed")
                except:
                    traceback.print_exc(self._log_file)
                    self._worker.update_status("failed")
            else:
                log("No autoscaling group name was set", self._log_file)
                self._worker.update_status("done")
        else:
            log("ERROR: ami_id not found. You must use the `buildimage` command first.", self._log_file)
            self._worker.update_status("failed")
