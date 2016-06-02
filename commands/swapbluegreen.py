from fabric.colors import green as _green, yellow as _yellow, red as _red

from ghost_log import log
from ghost_tools import get_aws_connection_data, get_app_friendly_name
from ghost_aws import check_autoscale_exists
from settings import cloud_connections, DEFAULT_PROVIDER

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

    def _get_blue_green_apps(self):
        app = self_.app
        if app.get('blue_green') and app['blue_green'].get('alter_ego_id'):
            alter_ego_app = self._worker._db.apps.find_one({ '_id': app['blue_green']['alter_ego_id']})
            if app['blue_green']['is_online']:
                return app, alter_ego_app
            else:
                if alter_ego_app['blue_green']['is_online']:
                    return alter_ego_app, app
                else:
                    return None, None
        else:
            return None, None

    def execute(self):
        log(_green("STATE: Started"), self._log_file)
        online_app, to_deploy_app = self._get_blue_green_apps()
        if not online_app:
            self._worker.update_status("aborted", message=self._get_notification_message_aborted(self._app, "Blue/green is not enabled on this app or not well configured"))
            return
        try:
            if not to_deploy_app['ami']:
                self._worker.update_status("aborted", message=self._get_notification_message_aborted(to_deploy_app, "Please run `Buildimage` first"))
                return
            if not (check_autoscale_exists(self._cloud_connection, to_deploy_app['autoscale']['name'], to_deploy_app['region'])
                and check_autoscale_exists(self._cloud_connection, online_app['autoscale']['name'], online_app['region'])):
                self._worker.update_status("aborted", message=self._get_notification_message_aborted(to_deploy_app, "Please set an AutoScale on both green and blue app"))
                return
            self._worker.update_status("done")#, message=self._get_notification_message_done(online_app, ))
        except GCallException as e:
            self._worker.update_status("failed", message=self._get_notification_message_failed(online_app, to_deploy_app, e))
