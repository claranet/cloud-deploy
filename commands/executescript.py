from fabric.colors import green as _green, yellow as _yellow, red as _red

from settings import cloud_connections, DEFAULT_PROVIDER

from ghost_log import log
from ghost_tools import get_aws_connection_data
from ghost_tools import b64decode_utf8, get_ghost_env_variables
from libs.host_deployment_manager import HostDeploymentManager
from libs.blue_green import get_blue_green_from_app

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

    def _get_module_path_and_uid(self, module_name):
        """
        Get the destination path for the given module, if any, '/tmp' otherwise
        Get the user ID for the given module, if any, "0" (root) otherwise
        """
        for item in self._app['modules']:
            if 'name' in item and item['name'] == module_name:
                return item['path'], item.get('uid', 0), item
        return '/tmp', 0, None

    def _exec_script(self, script, module_name, fabric_execution_strategy, safe_deployment_strategy):
        context_path, sudoer_uid, module = self._get_module_path_and_uid(module_name)
        ghost_env_vars = get_ghost_env_variables(self._app, module, self._color, self._job['user'])

        deploy_manager = HostDeploymentManager(self._cloud_connection, self._app, module, self._log_file,
                                               self._app['safe-deployment'], fabric_execution_strategy,
                                               'executescript', {
                                                   'script': script,
                                                   'context_path': context_path,
                                                   'sudoer_uid': sudoer_uid,
                                                   'jobid': self._job['_id'],
                                                   'env_vars': ghost_env_vars,
                                               })
        deploy_manager.deployment(safe_deployment_strategy)

    def execute(self):
        script = self._job['options'][0] if 'options' in self._job and len(self._job['options']) > 0 else None
        module_name = self._job['options'][1] if 'options' in self._job and len(self._job['options']) > 1 else None
        fabric_execution_strategy = self._job['options'][2] if 'options' in self._job and len(
            self._job['options']) > 2 else None
        safe_deployment_strategy = self._job['options'][3] if 'options' in self._job and len(
            self._job['options']) > 3 else None

        try:
            log(_green("STATE: Started"), self._log_file)
            try:
                if not script or not script.strip():
                    return self._abort("No valid script provided")
                script_data = b64decode_utf8(script)
                allowed_shebang = (
                    '#!/bin/bash',
                    '#! /bin/bash',
                    '#!/bin/sh',
                    '#! /bin/sh'
                )
                if not script_data.startswith(allowed_shebang):
                    return self._abort("No valid shell script provided (shebang missing)")
            except:
                return self._abort("No valid script provided")

            self._exec_script(script_data, module_name, fabric_execution_strategy, safe_deployment_strategy)

            self._worker.update_status("done", message=self._get_notification_message_done())
            log(_green("STATE: End"), self._log_file)
        except Exception as e:
            self._worker.update_status("failed", message=self._get_notification_message_failed(e))
            log(_red("STATE: End"), self._log_file)
