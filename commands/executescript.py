from fabric.colors import green as _green, yellow as _yellow, red as _red

from settings import cloud_connections, DEFAULT_PROVIDER

from ghost_log import log
from ghost_tools import get_aws_connection_data
from ghost_tools import b64decode_utf8
from libs.blue_green import get_blue_green_from_app
from libs.ec2 import find_ec2_running_instances
from libs.deploy import launch_exec_script

COMMAND_DESCRIPTION = "Execute a script/commands on every instance"

class Executescript():
    _app = None
    _job = None
    _log_file = -1

    def __init__(self, worker):
        self._app = worker.app
        self._job = worker.job
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

    def _get_notification_message_done(self):
        """
        >>> from bson.objectid import ObjectId
        >>> class worker:
        ...   app = {'name': 'app1'}
        ...   job = None
        ...   log_file = None
        ...   _config = None
        >>> Executescript(worker=worker())._get_notification_message_done()
        'Execute script OK for app [app1]'
        """
        return 'Execute script OK for app [{0}]'.format(self._app['name'])

    def _get_notification_message_failed(self, e):
        """
        >>> class worker:
        ...   app = {'name': 'app1'}
        ...   job = None
        ...   log_file = None
        ...   _config = None
        >>> Executescript(worker=worker())._get_notification_message_failed('Exception')
        'Execute script Failed for app [app1] Exception'
        >>> Executescript(worker=worker())._get_notification_message_failed('Exception-test')
        'Execute script Failed for app [app1] Exception-test'
        """
        return "Execute script Failed for app [{0}] {1}".format(self._app['name'], str(e))

    def _get_notification_message_aborted(self, message):
        """
        >>> class worker:
        ...   app = {'name': 'app1'}
        ...   job = None
        ...   log_file = None
        ...   _config = None
        >>> Executescript(worker=worker())._get_notification_message_aborted('No script provided')
        'Execute script Aborted for app [app1] - No script provided'
        >>> Executescript(worker=worker())._get_notification_message_aborted('Invalid module')
        'Execute script Aborted for app [app1] - Invalid module'
        """
        return "Execute script Aborted for app [{0}] - {1}".format(self._app['name'], message)

    def _abort(self, message):
        return self._worker.update_status("aborted", message=self._get_notification_message_aborted(message))

    def _get_module_path(self, module_name):
        """
        Get the destination path for the given module, or '/tmp' by default.
        """
        for item in self._app['modules']:
            if 'name' in item and item['name'] == module_name:
                return item['path']
        return '/tmp'

    def _exec_script(self, script, module_context, fabric_execution_strategy):
        context_path = self._get_module_path(module_context)
        running_instances = find_ec2_running_instances(self._cloud_connection, self._app['name'], self._app['env'], self._app['role'], self._app['region'], ghost_color=self._color)
        hosts_list = [host['private_ip_address'] for host in running_instances]
        launch_exec_script(self._app, script, context_path, hosts_list, fabric_execution_strategy, self._log_file)

    def execute(self):
        script = self._job['options'][0] if 'options' in self._job and len(self._job['options']) > 0 else None
        module_context = self._job['options'][1] if 'options' in self._job and len(self._job['options']) > 1 else None
        fabric_execution_strategy = self._job['options'][2] if 'options' in self._job and len(self._job['options']) > 2 else None

        try:
            log(_green("STATE: Started"), self._log_file)
            try:
                if not script or not script.strip():
                    return self._abort("No valid script provided")
                script_data = b64decode_utf8(script)
            except:
                return self._abort("No valid script provided")

            self._exec_script(script_data, module_context, fabric_execution_strategy)

            self._worker.update_status("done", message=self._get_notification_message_done())
            log(_green("STATE: End"), self._log_file)
        except Exception as e:
            self._worker.update_status("failed", message=self._get_notification_message_failed(e))
            log(_red("STATE: End"), self._log_file)
