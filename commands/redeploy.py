from bson.objectid import ObjectId

from ghost_tools import GCallException, gcall, get_app_module_name_list, clean_local_module_workspace
from ghost_tools import get_aws_connection_data
from settings import cloud_connections, DEFAULT_PROVIDER
from ghost_log import log
from libs.host_deployment_manager import HostDeploymentManager
from libs.deploy import execute_module_script_on_ghost
from libs.deploy import update_app_manifest, rollback_app_manifest
from ghost_tools import get_path_from_app_with_color, get_buildpack_clone_path_from_module

COMMAND_DESCRIPTION = "Re-deploy an old module package"
RELATED_APP_FIELDS = []


def is_available(app_context=None):
    return True


class Redeploy():
    _app = None
    _job = None
    _log_file = -1
    _config = None

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

    def _find_modules_by_name(self, modules):
        result = []
        for module in modules:
            if 'name' in module:
                for item in self._app['modules']:
                    if 'name' in item and item['name'] == module['name']:
                        result.append(item)
        return result

    def _get_deploy_infos(self, deploy_id):
        deploy_infos = self._db.deploy_histories.find_one({'_id': ObjectId(deploy_id)})
        if deploy_infos:
            module = {}
            module['path'] = deploy_infos['module_path']
            module['name'] = deploy_infos['module']
            return module, deploy_infos['package']
        return None, None

    def _deploy_module(self, module, fabric_execution_strategy, safe_deployment_strategy):
        deploy_manager = HostDeploymentManager(self._cloud_connection, self._app, module, self._log_file,
                                               self._app['safe-deployment'], fabric_execution_strategy)
        deploy_manager.deployment(safe_deployment_strategy)

    def _local_extract_package(self, module, package):
        clone_path = get_buildpack_clone_path_from_module(self._app, module)
        gcall('rm -rf "%s"' % clone_path, 'Cleaning old temporary redeploy module working directory "%s"' % clone_path, self._log_file)
        gcall('mkdir -p "%s"' % clone_path, 'Recreating redeploy module working directory "%s"' % clone_path, self._log_file)

        key_path = '{path}/{module}/{pkg_name}'.format(path=get_path_from_app_with_color(self._app), module=module['name'], pkg_name=package)
        log("Downloading package: {0} from '{1}'".format(package, key_path), self._log_file)
        dest_package_path = "{0}/{1}".format(clone_path, package)
        cloud_connection = cloud_connections.get(self._app.get('provider', DEFAULT_PROVIDER))(self._log_file)
        conn = cloud_connection.get_connection(self._config.get('bucket_region', self._app['region']), ["s3"])
        bucket = conn.get_bucket(self._config['bucket_s3'])
        key = bucket.get_key(key_path)
        if not key:
            raise GCallException("Package '{0}' doesn't exist on bucket '{1}'".format(key_path, self._config['bucket_s3']))
        key.get_contents_to_filename(dest_package_path)

        gcall('tar -xf "{0}" -C "{1}"'.format(dest_package_path, clone_path), "Extracting package: %s" % package, self._log_file)
        return clone_path

    def _execute_redeploy(self, deploy_id, fabric_execution_strategy, safe_deployment_strategy):
        module, package = self._get_deploy_infos(deploy_id)
        if module and package:
            before_update_manifest = update_app_manifest(self._app, self._config, module, package, self._log_file)
            all_app_modules_list = get_app_module_name_list(self._app['modules'])
            clean_local_module_workspace(get_path_from_app_with_color(self._app), all_app_modules_list, self._log_file)
            # Download and extract package before launching deploy
            clone_path = self._local_extract_package(module, package)

            try:
                # Re-deploy
                self._deploy_module(module, fabric_execution_strategy, safe_deployment_strategy)
            except GCallException as e:
                log("Redeploy error occured, app manifest will be restored to its previous state", self._log_file)
                rollback_app_manifest(self._app, self._config, before_update_manifest, self._log_file)
                raise e

            # After all deploy exec
            execute_module_script_on_ghost(self._app, module, 'after_all_deploy', 'After all deploy', clone_path, self._log_file)
        else:
            raise GCallException("Redeploy on deployment ID: {0} failed".format(deploy_id))

    def execute(self):
        log("Redeploying module", self._log_file)
        if 'options' in self._job and len(self._job['options']) > 0:
            deploy_id = self._job['options'][0]
            fabric_execution_strategy = self._job['options'][1] if len(self._job['options']) > 0 else None
            safe_deployment_strategy = self._job['options'][2] if len(self._job['options']) > 2 else None
            try:
                self._execute_redeploy(deploy_id, fabric_execution_strategy, safe_deployment_strategy)
                self._worker.update_status("done", message="Redeploy OK: [{0}]".format(deploy_id))
            except GCallException as e:
                self._worker.update_status("failed", message="Redeploy Failed: [{0}]\n{1}".format(deploy_id, str(e)))
        else:
            self._worker.update_status("failed", message="Incorrect job request: missing options field deploy_id")
