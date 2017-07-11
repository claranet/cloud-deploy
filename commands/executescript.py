from fabric.colors import green as _green, yellow as _yellow, red as _red

from settings import cloud_connections, DEFAULT_PROVIDER

from ghost_log import log
from ghost_tools import get_aws_connection_data, GCallException, boolify
from ghost_tools import b64decode_utf8, get_ghost_env_variables
from libs.host_deployment_manager import HostDeploymentManager
from libs.blue_green import get_blue_green_from_app
from libs.ec2 import get_ec2_instance
from libs.deploy import launch_executescript

COMMAND_DESCRIPTION = "Execute a script/commands on every instance"
RELATED_APP_FIELDS = []


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

    def _exec_script_single_host(self, script, module_name, single_host_ip):
        context_path, sudoer_uid, module = self._get_module_path_and_uid(module_name)
        ghost_env_vars = get_ghost_env_variables(self._app, module, self._color, self._job['user'])

        ec2_obj = get_ec2_instance(self._cloud_connection, self._app['region'], {
            'private-ip-address': single_host_ip,
            'vpc-id': self._app['vpc_id'],
        })
        if not ec2_obj or ec2_obj.vpc_id!= self._app['vpc_id'] or ec2_obj.private_ip_address != single_host_ip:
            raise GCallException("Cannot found the single instance with private IP '{ip}' in VPC '{vpc}'".format(ip=single_host_ip, vpc=self._app['vpc_id']))
        if ec2_obj.tags['app'] != self._app['name'] or ec2_obj.tags['env'] != self._app['env'] or ec2_obj.tags['role'] != self._app['role']:
            raise GCallException("Cannot execute script on this instance ({ip} - {id}), invalid Ghost tags".format(ip=single_host_ip, id=ec2_obj.id))

        log("EC2 instance found, ready to execute script ({ip} - {id} - {name})".format(ip=single_host_ip, id=ec2_obj.id, name=ec2_obj.tags.get('Name', '')), self._log_file)
        launch_executescript(self._app, script, context_path, sudoer_uid, self._job['_id'], [single_host_ip], 'serial', self._log_file, ghost_env_vars)

    def execute(self):
        if not boolify(self._config.get('enable_executescript_command', True)):
            return self._abort("This command has been disabled by your administrator.")
        script = self._job['options'][0] if 'options' in self._job and len(self._job['options']) > 0 else None
        module_name = self._job['options'][1] if 'options' in self._job and len(self._job['options']) > 1 else None
        execution_strategy = self._job['options'][2] if 'options' in self._job and len(self._job['options']) > 2 else None
        if execution_strategy == 'single':
            # option[3] is a single Host IP
            fabric_execution_strategy = None
            safe_deployment_strategy = None
            single_host_ip = self._job['options'][3] if 'options' in self._job and len(self._job['options']) > 3 else None
        else:
            # option[2] is fabric type, option[3] might be Safe deploy group param
            fabric_execution_strategy = execution_strategy
            safe_deployment_strategy = self._job['options'][3] if 'options' in self._job and len(self._job['options']) > 3 else None
            single_host_ip = None

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

            if single_host_ip:
                log(_yellow("Executing script on a single host: %s" % single_host_ip), self._log_file)
                self._exec_script_single_host(script_data, module_name, single_host_ip)
            else:
                log(_yellow("Executing script on every running instance"), self._log_file)
                self._exec_script(script_data, module_name, fabric_execution_strategy, safe_deployment_strategy)

            self._worker.update_status("done", message=self._get_notification_message_done())
            log(_green("STATE: End"), self._log_file)
        except Exception as e:
            self._worker.update_status("failed", message=self._get_notification_message_failed(e))
            log(_red("STATE: End"), self._log_file)
