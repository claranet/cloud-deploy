import base64
import sys
import traceback

from boto import s3

from commands.tools import refresh_stage2

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

    def execute(self):
        try:
            app = self._app
            bucket = self._config['bucket_s3']
            refresh_stage2(bucket, app['region'], self._config['ghost_root_path'])

            # Store lifecycle hooks scripts in S3
            lifecycle_hooks = app.get('lifecycle_hooks', None)
            if lifecycle_hooks is not None:
                conn = s3.connect_to_region(app['region'])
                bucket = conn.get_bucket(bucket)

                prefix = '/ghost/{app}/{env}/{role}'.format(app=app['name'], env=app['env'], role=app['role'])
                if 'pre_bootstrap' in lifecycle_hooks:
                    pre_bootstrap_source = base64.b64decode(lifecycle_hooks['pre_bootstrap'])
                    k = bucket.new_key('{prefix}/pre_bootstrap'.format(prefix=prefix))
                    k.set_contents_from_string(pre_bootstrap_source)

                if 'post_bootstrap' in lifecycle_hooks:
                    post_bootstrap_source = base64.b64decode(lifecycle_hooks['post_bootstrap'])
                    k = bucket.new_key('{prefix}/post_bootstrap'.format(prefix=prefix))
                    k.set_contents_from_string(post_bootstrap_source)

            self._worker.update_status("done", message="Scripts Update OK")
        except:
            traceback.print_exc(self._log_file)
            self._worker.update_status("failed", message="Scripts Update Failed: {1}".format(str(sys.exc_info()[1])))