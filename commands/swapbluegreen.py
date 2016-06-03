from fabric.colors import green as _green, yellow as _yellow, red as _red

from ghost_log import log
from ghost_tools import get_aws_connection_data, get_app_friendly_name
from ghost_aws import check_autoscale_exists
from settings import cloud_connections, DEFAULT_PROVIDER
from libs.blue_green import get_blue_green_apps, check_app_manifest

COMMAND_DESCRIPTION = "Swap the Blue/Green env"

class Swapbluegreen():
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

    def _get_notification_message_failed(self, online_app, to_deploy_app, e):
        app_name = get_app_friendly_name(online_app)
        notif = "Blue/green swap failed for [{0}] between [{1}] and [{2}]: {3}".format(app_name, online_app['_id'], to_deploy_app['_id'], str(e))
        return _red(notif)

    def _get_notification_message_aborted(self, app, msg):
        notif = "Blue/green swap aborted for [{0}] : {1}".format(get_app_friendly_name(app), msg)
        return _yellow(notif)

    def _get_notification_message_done(self, online_app, as_old, as_new, elb_name, elb_dns):
        app_name = get_app_friendly_name(online_app)
        notif = "Blue/green swap done for [{0}] between [{1}] and [{2}] on ELB '{3}' ({4})".format(app_name, as_old, as_new, elb_name, elb_dns)
        return _green(notif)

    def execute(self):
        log(_green("STATE: Started"), self._log_file)
        swap_execution_strategy = self._job['options'][0] if 'options' in self._job and len(self._job['options']) > 0 else None
        online_app, to_deploy_app = get_blue_green_apps(self._app,
                                                        self._worker._db.apps)
        if not online_app:
            self._worker.update_status("aborted", message=self._get_notification_message_aborted(self._app, "Blue/green is not enabled on this app or not well configured"))
            return
        try:
            # Check AMI
            if 'ami' not in to_deploy_app:
                self._worker.update_status("aborted", message=self._get_notification_message_aborted(to_deploy_app, "Please run `Buildimage` first"))
                return
            # Check ASG
            if to_deploy_app['autoscale']['name'] and online_app['autoscale']['name']:
                if not (check_autoscale_exists(self._cloud_connection, to_deploy_app['autoscale']['name'], to_deploy_app['region'])
                    and check_autoscale_exists(self._cloud_connection, online_app['autoscale']['name'], online_app['region'])):
                    self._worker.update_status("aborted", message=self._get_notification_message_aborted(to_deploy_app, "Please set an AutoScale on both green and blue app"))
                    return
            else:
                self._worker.update_status("aborted", message=self._get_notification_message_aborted(offline_app, "Please set an AutoScale on both green and blue app."))
                return
            # Check if modules have been deployed
            if not check_app_manifest(to_deploy_app, self._config, self._log_file):
                self._worker.update_status("aborted", message=self._get_notification_message_aborted(to_deploy_app, "Please deploy your app's modules"))
                return
            # Check if we're ready to swap
            self._worker.update_status("done")#, message=self._get_notification_message_done(online_app, ))
        except GCallException as e:
            self._worker.update_status("failed", message=self._get_notification_message_failed(online_app, to_deploy_app, e))
