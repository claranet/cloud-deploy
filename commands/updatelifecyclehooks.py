import base64
import sys
import traceback

from boto import s3

from commands.tools import log
from ghost_tools import refresh_stage2

class Updatelifecyclehooks():
    _app = None
    _job = None
    _log_file = -1
    _worker = None
    _config = None

    def __init__(self, worker):
        self._app = worker.app
        self._job = worker.job
        self._log_file = worker.log_file
        self._config = worker._config
        self._worker = worker


    def _refresh_lifecycle_hook_script(self, lifecycle_hook, lifecycle_hooks, bucket, prefix):
        key_name = '{prefix}/{lifecycle_hook}'.format(prefix=prefix, lifecycle_hook=lifecycle_hook)
        lifecycle_hook_source = lifecycle_hooks is not None and lifecycle_hooks.get(lifecycle_hook, None)
        if lifecycle_hook_source:
            lifecycle_hook_source = base64.b64decode(lifecycle_hook_source)
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
            refresh_stage2(self._config['bucket_region'] or self._app['region'], self._config)
            log('INFO: refreshed /ghost/stage2', self._log_file)

            # Store lifecycle hooks scripts in S3
            lifecycle_hooks = app.get('lifecycle_hooks', None)
            conn = s3.connect_to_region(self._config['bucket_region'] or app['region'])
            bucket = conn.get_bucket(self._config['bucket_s3'])
            prefix = '/ghost/{app}/{env}/{role}'.format(app=app['name'], env=app['env'], role=app['role'])
            self._refresh_lifecycle_hook_script('pre_bootstrap', lifecycle_hooks, bucket, prefix)
            self._refresh_lifecycle_hook_script('post_bootstrap', lifecycle_hooks, bucket, prefix)

            self._worker.update_status("done", message="Scripts Update OK")
        except:
            traceback.print_exc(self._log_file)
            self._worker.update_status("failed", message="Scripts Update Failed: {0}".format(str(sys.exc_info()[1])))
