from fabric.colors import green as _green, yellow as _yellow, red as _red

from settings import cloud_connections, DEFAULT_PROVIDER

from ghost_log import log
from ghost_tools import get_aws_connection_data
from libs.blue_green import get_blue_green_from_app
from libs.ec2 import create_ec2_instance

COMMAND_DESCRIPTION = "Create a new instance"
RELATED_APP_FIELDS = ['environment_infos']


def is_available(app_context=None):
    if not app_context:
        return True
    return app_context.get('ami', '') != ''


class Createinstance():
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
        subnet_id = self._job['options'][0] if 'options' in self._job and len(self._job['options']) > 0 else self._app['environment_infos']['subnet_ids'][0]
        private_ip_address = self._job['options'][1] if 'options' in self._job and len(self._job['options']) > 1 else None

        try:
            log(_green("STATE: Started"), self._log_file)
            instance = create_ec2_instance(self._cloud_connection, self._app, self._color, self._config,
                                           private_ip_address, subnet_id,
                                           self._log_file)
            self._worker.update_status("done", message="Creating Instance OK: [{0}]\n\nPublic IP: {1}".format(self._app['name'], str(instance.ip_address)))
            log(_green("STATE: End"), self._log_file)
        except Exception as e:
            self._worker.update_status("failed", message="Creating Instance Failed: [{0}]\n{1}".format(self._app['name'], e))
            log(_red("STATE: END"), self._log_file)
