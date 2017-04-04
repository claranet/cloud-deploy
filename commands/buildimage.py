import json
import io
import os
import traceback

from ghost_log import log
from ghost_aws import create_userdata_launchconfig_update_asg
from ghost_tools import get_aws_connection_data
from settings import cloud_connections, DEFAULT_PROVIDER
from libs.deploy import touch_app_manifest
from libs.image_builder_aws import AWSImageBuilder

COMMAND_DESCRIPTION = "Build Image"

class Buildimage():
    _app = None
    _job = None
    _log_file = -1

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
        self._aws_image_builder = AWSImageBuilder(self._app, self._job, self._db, self._log_file, self._config)


    def _get_notification_message_done(self, ami_id):
        """
        >>> from bson.objectid import ObjectId
        >>> class worker:
        ...   app = {'name': 'AppName', 'env': 'prod', 'role': 'webfront', 'region': 'eu-west-1'}
        ...   job = None
        ...   log_file = None
        ...   _config = None
        ...   _db = None
        >>> Buildimage(worker=worker())._get_notification_message_done('')
        'Build image OK: []'
        >>> Buildimage(worker=worker())._get_notification_message_done('012345678901234567890123')
        'Build image OK: [012345678901234567890123]'
        """
        return 'Build image OK: [{0}]'.format(ami_id)

    def _update_app_ami(self, ami_id, ami_name):
        self._db.apps.update({'_id': self._app['_id']},{'$set': {'ami': ami_id, 'build_infos.ami_name': ami_name}})
        self._worker.update_status("done")

    def execute(self):
        ami_id, ami_name = self._aws_image_builder._start_packer()
        if ami_id is not "ERROR":
            touch_app_manifest(self._app, self._config, self._log_file)
            log("Update app in MongoDB to update AMI: {0}".format(ami_id), self._log_file)
            self._update_app_ami(ami_id, ami_name)
            if (self._aws_image_builder._purge_old_images()):
                log("Old AMIs removed for this app", self._log_file)
            else:
                log("Purge old AMIs failed", self._log_file)
            if self._app['autoscale']['name']:
                try:
                    if create_userdata_launchconfig_update_asg(ami_id, self._cloud_connection, self._app, self._config, self._log_file):
                        self._worker.update_status("done", message=self._get_notification_message_done(ami_id))
                    else:
                        self._worker.update_status("failed")
                except:
                    traceback.print_exc(self._log_file)
                    self._worker.update_status("failed")
            else:
                log("No autoscaling group name was set", self._log_file)
                self._worker.update_status("done")
        else:
            log("ERROR: ami_id not found. The packer process had maybe fail.", self._log_file)
            self._worker.update_status("failed")
