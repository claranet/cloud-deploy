import sys
import traceback

from ghost_tools import refresh_stage2
from ghost_log import log
from ghost_aws import create_launch_config, generate_userdata, check_autoscale_exists, purge_launch_configuration, update_auto_scale
from settings import cloud_connections, DEFAULT_PROVIDER
from ghost_tools import get_aws_connection_data
from ghost_tools import b64decode_utf8
from libs.deploy import get_path_from_app_with_color

COMMAND_DESCRIPTION = "Update LifeCycle Hooks scripts"

class Updatelifecyclehooks():
    _app = None
    _job = None
    _log_file = -1
    _worker = None
    _config = None
    _cloud_connection = None

    def __init__(self, worker):
        self._app = worker.app
        self._job = worker.job
        self._log_file = worker.log_file
        self._config = worker._config
        self._worker = worker
        self._connection_data = get_aws_connection_data(
                self._app.get('assumed_account_id', ''),
                self._app.get('assumed_role_name', ''),
                self._app.get('assumed_region_name', '')
                )
        self._cloud_connection = cloud_connections.get(self._app.get('provider', DEFAULT_PROVIDER))(
                self._log_file,
                **self._connection_data
                )

    def _refresh_env_vars(self, custom_env_vars, bucket, prefix):
        key_name = '{prefix}/{var_file}'.format(prefix=prefix, var_file='custom_env_vars')
        env_vars_source = u"""
#!/bin/bash

"""
        env_vars_source = env_vars_source + u''.join([u'export {key}="{val}" \n'.format(key=env_var['var_key'], val=env_var['var_value']) for env_var in custom_env_vars])

        k = bucket.new_key(key_name)
        k.set_contents_from_string(env_vars_source)
        k.close()

        log('INFO: uploaded {key}'.format(key=key_name), self._log_file)

    def _refresh_lifecycle_hook_script(self, lifecycle_hook, lifecycle_hooks, bucket, prefix):
        key_name = '{prefix}/{lifecycle_hook}'.format(prefix=prefix, lifecycle_hook=lifecycle_hook)
        lifecycle_hook_source = lifecycle_hooks is not None and lifecycle_hooks.get(lifecycle_hook, None)
        if lifecycle_hook_source:
            lifecycle_hook_source = b64decode_utf8(lifecycle_hook_source)
            k = bucket.new_key(key_name)
            k.set_contents_from_string(lifecycle_hook_source)
            k.close()
            log('INFO: uploaded {key}'.format(key=key_name), self._log_file)
        else:
            bucket.delete_key(key_name)
            log('INFO: deleted {key}'.format(key=key_name), self._log_file)


    def execute(self):
        try:
            app = self._app
            cloud_connection = cloud_connections.get(self._app.get('provider', DEFAULT_PROVIDER))(self._log_file)
            refresh_stage2(cloud_connection, self._config.get('bucket_region', self._app['region']), self._config)
            log('INFO: refreshed /ghost/stage2', self._log_file)

            # Store lifecycle hooks scripts in S3
            lifecycle_hooks = app.get('lifecycle_hooks', None)
            conn = cloud_connection.get_connection(self._config.get('bucket_region', self._app['region']), ["s3"])
            bucket = conn.get_bucket(self._config['bucket_s3'])
            prefix = get_path_from_app_with_color(app)
            self._refresh_env_vars(app.get('env_vars', []), bucket, prefix)
            self._refresh_lifecycle_hook_script('pre_bootstrap', lifecycle_hooks, bucket, prefix)
            self._refresh_lifecycle_hook_script('post_bootstrap', lifecycle_hooks, bucket, prefix)

            # Update Auto-Scaling Launch Configuration if possible
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
                                update_auto_scale(self._cloud_connection, self._app, launch_config, self._log_file)
                                if (purge_launch_configuration(self._cloud_connection, self._app, self._config.get('launch_configuration_retention', 5))):
                                    log("Old launch configurations removed for this app", self._log_file)
                                else:
                                    log("ERROR: Purge launch configurations failed", self._log_file)
                            else:
                                log("ERROR: Cannot update autoscaling group", self._log_file)
                        else:
                            log("ERROR: Cannot generate userdata. The bootstrap.sh file can maybe not be found.", self._log_file)
                    else:
                        log("ERROR: Autoscaling group [{0}] does not exist".format(self._app['autoscale']['name']), self._log_file)
                else:
                    log("No autoscaling group name was set. No need to update LC.", self._log_file)
            else:
                log("WARNING: ami_id not found. You must use the `buildimage` command first.", self._log_file)

            self._worker.update_status("done", message="Scripts Update OK")
        except:
            traceback.print_exc(self._log_file)
            self._worker.update_status("failed", message="Scripts Update Failed: {0}".format(str(sys.exc_info()[1])))
