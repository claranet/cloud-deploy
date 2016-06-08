from fabric.colors import green as _green, yellow as _yellow, red as _red

from ghost_log import log
from ghost_tools import get_aws_connection_data, get_app_friendly_name
from settings import cloud_connections, DEFAULT_PROVIDER
from libs.ec2 import destroy_ec2_instances

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

    def _destroy_server(self):
        log(_green("STATE: Started"), self._log_file)
        log(_yellow(" INFO: Destroy all EC2 instances related to app {0} [{1}]".format(get_app_friendly_name(self._app), self._app['_id'])), self._log_file)
        log(" CONF: Region: {0}".format(self._app['region']), self._log_file)
        try:
            conn = self._cloud_connection.get_connection(self._app['region'], ["ec2"])
            destroy_ec2_instances(conn, self._app, self._log_file)

            self._worker.update_status("done", message="Instance deletion OK: [{0}]".format(self._app['name']))
            log(_green("STATE: End"), self._log_file)
        except IOError as e:
            log(_red("I/O error({0}): {1}".format(e.errno, e.strerror)), self._log_file)
            self._worker.update_status("failed", message="Creating Instance Failed: [{0}]\n{1}".format(self._app['name'], str(e)))
            log(_red("STATE: END"), self._log_file)

    def execute(self):
        self._destroy_server()
