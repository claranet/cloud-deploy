from fabric.colors import green as _green, yellow as _yellow, red as _red

from ghost_log import log
from ghost_tools import get_aws_connection_data, get_app_friendly_name
from ghost_aws import check_autoscale_exists
from settings import cloud_connections, DEFAULT_PROVIDER
from libs.ec2 import destroy_ec2_instances
from libs.safe_destroy import SafeDestroy

COMMAND_DESCRIPTION = "Destroy all instances"

class Destroyallinstances():
    _app = None
    _job = None
    _log_file = -1

    def __init__(self, worker):
        self._app = worker.app
        self._job = worker.job
        self._db = worker._db
        self._config = worker._config
        self._worker = worker
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

    def _destroy_instances(self, safe_destroy_strategy):
        log(_green("STATE: Started"), self._log_file)
        log(" CONF: Region: {0}".format(self._app['region']), self._log_file)

        try:
            if safe_destroy_strategy:
                log(_yellow(" INFO: Destroy all EC2 instances related to app {0} [{1}] using safe destroy strategy ({2})".format(get_app_friendly_name(self._app), self._app['_id'], safe_destroy_strategy)), self._log_file)
                as_conn = self._cloud_connection.get_connection(self._app['region'], ['autoscaling'], boto_version='boto3')
                if not self._app['autoscale']['name'] or not check_autoscale_exists(self._cloud_connection, self._app['autoscale']['name'], self._app['region']):
                    self._worker.update_status("aborted", message=_yellow(" WARNING: No AutoScale specified, cannot use Safe destroy strategy"))
                    return

                safedestroy = SafeDestroy(self._cloud_connection, self._app, self._app['safe-deployment'], self._log_file)
                safedestroy.safe_manager(safe_destroy_strategy)
            else:
                log(_yellow(" INFO: Destroy all EC2 instances related to app {0} [{1}]".format(get_app_friendly_name(self._app), self._app['_id'])), self._log_file)
                destroy_ec2_instances(self._cloud_connection, self._app, self._log_file)

            self._worker.update_status("done", message="Instance deletion OK: [{0}]".format(self._app['name']))
            log(_green("STATE: End"), self._log_file)
        except Exception as e:
            self._worker.update_status("failed", message="Destroy instance Failed: [{0}]\n{1}".format(self._app['name'], str(e)))
            log(_red("STATE: End"), self._log_file)

    def execute(self):
        safe_destroy_strategy = self._job['options'][0] if 'options' in self._job and len(self._job['options']) > 0 else None
        self._destroy_instances(safe_destroy_strategy)
