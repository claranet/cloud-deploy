import traceback

from ghost_aws import create_userdata_launchconfig_update_asg
from ghost_log import log
from ghost_tools import get_aws_connection_data, GCallException

from libs.builders.image_builder_aws import AWSImageBuilder
from libs.builders.image_builder_lxd import LXDImageBuilder
from libs.deploy import touch_app_manifest, get_path_from_app_with_color
from libs.lxd import lxd_is_available

from libs.provisioners.provisioner_ansible import GalaxyNoMatchingRolesException, GalaxyBadRequirementPathException

from settings import cloud_connections, DEFAULT_PROVIDER

COMMAND_DESCRIPTION = "Build Image"
RELATED_APP_FIELDS = ['features', 'build_infos']


def is_available(app_context=None):
    return True


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
        self.job = {"id": self._job['_id'],
                    "instance_type": self._job['instance_type'],
                    "options": self._job['options']}
        self._aws_image_builder = AWSImageBuilder(self._app, self.job, self._db, self._log_file, self._config)
        self._lxd_image_builder = None
        if lxd_is_available() and self._app.get('build_infos', {}).get('source_container_image', None):
            self._lxd_image_builder = LXDImageBuilder(self._app, self.job, self._db, self._log_file, self._config)

    def _get_notification_message_done(self, ami_id):
        """
        >>> class worker:
        ...   app = { '_id': "987654321098765432109876" ,'name': 'AppName', 'env': 'prod', 'role': 'webfront', 'region': 'eu-west-1' }
        ...   job = { '_id': "012345678901234567890123" , "options" : "True" , "instance_type" : None}
        ...   log_file = None
        ...   _config = {}
        ...   _db = None
        >>> Buildimage(worker=worker())._get_notification_message_done('')
        'Build image OK: []'
        >>> Buildimage(worker=worker())._get_notification_message_done('012345678901234567890123')
        'Build image OK: [012345678901234567890123]'
        """
        return 'Build image OK: [{0}]'.format(ami_id)

    def _update_app_ami(self, ami_id, ami_name):
        self._db.apps.update({'_id': self._app['_id']}, {'$set': {'ami': ami_id, 'build_infos.ami_name': ami_name}})
        self._worker.update_status("done")

    def _update_container_source(self, container):
        self._db.apps.update({'_id': self._app['_id']}, {'$set': {'build_infos.container_image': str(container)}})

    def execute(self):
        try:
            ami_id, ami_name = self._aws_image_builder.start_builder()
            if ami_id is "ERROR":
                log("ERROR: ami_id not found. The packer process had maybe fail.", self._log_file)
                self._worker.update_status("failed")
                return
        except (GalaxyNoMatchingRolesException, GalaxyBadRequirementPathException, GCallException) as e:
            self._worker.update_status("aborted", message=str(e))
            return

        touch_app_manifest(self._app, self._config, self._log_file)
        log("Update app in MongoDB to update AMI: {0}".format(ami_id), self._log_file)
        self._update_app_ami(ami_id, ami_name)
        if self._aws_image_builder.purge_old_images():
            log("Old AMIs removed for this app", self._log_file)
        else:
            log("Purge old AMIs failed", self._log_file)

        if self._lxd_image_builder:
            log("Generating a new container", self._log_file)
            try:
                self._lxd_image_builder.set_source_hooks(get_path_from_app_with_color(self._app))
                self._lxd_image_builder.start_builder()
            except Exception as e:
                traceback.print_exc(self._log_file)
                log("An error occured during container process ({})".format(e), self._log_file)
                self._worker.update_status("failed")
                return
            log("Update app in MongoDB to update container source image", self._log_file)
            self._update_container_source(self.job["id"])

        if self._app['autoscale']['name']:
            try:
                if create_userdata_launchconfig_update_asg(ami_id, self._cloud_connection, self._app, self._config,
                                                           self._log_file):
                    self._worker.update_status("done", message=self._get_notification_message_done(ami_id))
                else:
                    self._worker.update_status("failed")
            except:
                traceback.print_exc(self._log_file)
                self._worker.update_status("failed")
        else:
            log("No autoscaling group name was set", self._log_file)
            self._worker.update_status("done")
