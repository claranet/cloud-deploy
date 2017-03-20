from fabric.colors import green as _green, yellow as _yellow, red as _red

from settings import cloud_connections, DEFAULT_PROVIDER

from ghost_log import log
from ghost_tools import get_aws_connection_data, get_app_friendly_name
from ghost_aws import check_autoscale_exists
from libs.blue_green import get_blue_green_from_app
from libs.ec2 import create_ec2_instance, destroy_ec2_instances
from libs.rolling_update import RollingUpdate

COMMAND_DESCRIPTION = "Recreate all the instances, rolling update possible when using an Autoscale"

class Recreateinstances():
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
        blue_green, self._color = get_blue_green_from_app(self._app)

    def execute(self):
        try:
            log(_green("STATE: Started"), self._log_file)
            rolling_update_strategy = self._job['options'][0] if 'options' in self._job and len(self._job['options']) > 0 else None

            as_conn = self._cloud_connection.get_connection(self._app['region'], ['autoscaling'], boto_version='boto3')
            if not self._app['autoscale']['name'] or not check_autoscale_exists(self._cloud_connection, self._app['autoscale']['name'], self._app['region']):
                log(_yellow(" INFO: No AutoScale specified, this command will destroy and recreate standalone instances"), self._log_file)

                destroyed_count, destroyed_instances_info = destroy_ec2_instances(self._cloud_connection, self._app, self._log_file, "running")
                x = 0
                while x < destroyed_count:
                    create_ec2_instance(self._cloud_connection, self._app, self._color, self._config,
                                        destroyed_instances_info[x]['private_ip_address'], destroyed_instances_info[x]['subnet_id'],
                                        self._log_file)
                    x += 1

                self._worker.update_status("done", message="Re-create instances OK: [{0}]".format(self._app['name']))
                log(_green("STATE: End"), self._log_file)
            else:
                if rolling_update_strategy:
                    log(_yellow(" INFO: Destroy all EC2 instances related to app {0} [{1}] using rolling update strategy ({2})".format(get_app_friendly_name(self._app), self._app['_id'], rolling_update_strategy)), self._log_file)
                else:
                    log(_yellow(" INFO: Destroy all EC2 instances related to app {0} [{1}] and let the AutoScale ({2}) recreate them".format(get_app_friendly_name(self._app), self._app['_id'], self._app['autoscale']['name'])), self._log_file)

                safedestroy = RollingUpdate(self._cloud_connection, self._app, self._app['safe-deployment'], self._log_file)
                safedestroy.do_rolling(rolling_update_strategy)

                self._worker.update_status("done", message="Re-create instances OK: [{0}]".format(self._app['name']))
                log(_green("STATE: End"), self._log_file)

        except Exception as e:
            self._worker.update_status("failed", message="Re-create instances Failed: [{0}]\n{1}".format(self._app['name'], str(e)))
            log(_red("STATE: END"), self._log_file)
            raise
