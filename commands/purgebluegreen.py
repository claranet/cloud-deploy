from fabric.colors import green as _green, yellow as _yellow, red as _red

from ghost_log import log
from ghost_tools import get_aws_connection_data, get_app_friendly_name, GCallException
from settings import cloud_connections, DEFAULT_PROVIDER

from ghost_aws import check_autoscale_exists
from libs.elb import get_elb_instance_status_autoscaling_group, get_elb_from_autoscale
from libs.autoscaling import get_instances_from_autoscaling
from libs.blue_green import get_blue_green_apps

COMMAND_DESCRIPTION = "Purge the Blue/Green env"

class Purgebluegreen():
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

    def _get_notification_message_failed(self, app, msg):
        notif = "Blue/green purge failed for [{0}] : {1}".format(get_app_friendly_name(app), msg)
        return _red(notif)

    def _get_notification_message_aborted(self, app, msg):
        notif = "Blue/green purge aborted for [{0}] : {1}".format(get_app_friendly_name(app), msg)
        return _yellow(notif)

    def _get_notification_message_done(self, app):
        app_name = get_app_friendly_name(app)
        notif = "Blue/green purge done for [{0}]".format(app_name)
        return _green(notif)

    def execute(self):
        log(_green("STATE: Started"), self._log_file)
        online_app, offline_app = get_blue_green_apps(self._app,
                                                        self._worker._db.apps)
        if not offline_app:
            self._worker.update_status("aborted", message=self._get_notification_message_aborted(self._app, "Blue/green is not enabled on this app or not well configured"))
            return
        try:
            # Check ASG
            if to_deploy_app['autoscale']['name'] and online_app['autoscale']['name']:
                if not (check_autoscale_exists(self._cloud_connection, to_deploy_app['autoscale']['name'], to_deploy_app['region'])
                    and check_autoscale_exists(self._cloud_connection, online_app['autoscale']['name'], online_app['region'])):
                    self._worker.update_status("aborted", message=self._get_notification_message_aborted(to_deploy_app, "Not AutoScale group found on the offline app to purge."))
                    return
            else:
                self._worker.update_status("aborted", message=self._get_notification_message_aborted(offline_app, "Not AutoScale group found on the offline app to purge."))
                return

            as_conn3 = self._cloud_connection.get_connection(app_region, ['autoscaling'], boto_version='boto3')
            # Check if instances are running
            if not get_instances_from_autoscaling(offline_app['autoscale']['name'], as_conn):
                self._worker.update_status("aborted", message=self._get_notification_message_aborted(offline_app, "Autoscaling Group of offline app is empty. Nothing to do"))
                return

            # All good
            done_notif = self._get_notification_message_done(online_app, online_app['autoscale']['name'], to_deploy_app['autoscale']['name'], elb_name, elb_dns)
            self._worker.update_status("done", message=done_notif)
        except GCallException as e:
            self._worker.update_status("failed", message=self._get_notification_message_failed(online_app, to_deploy_app, str(e)))
