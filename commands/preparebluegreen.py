"""Classes pertaining to blue/green preparation."""
from fabric.colors import green as _green, yellow as _yellow, red as _red

from ghost_log import log
from ghost_tools import get_app_friendly_name
from libs.blue_green import get_blue_green_apps


COMMAND_DESCRIPTION = "Prepare the Blue/Green env before swap"


class Preparebluegreen(object):
    """Checks and prepares blue/green deployment before swap."""

    _app = None
    _job = None
    _log_file = -1

    def __init__(self, worker):
        """init from worker attributes."""
        self._app = worker.app
        self._job = worker.job
        self._db = worker._db
        self._config = worker._config
        self._worker = worker
        self._log_file = worker.log_file

    def _get_notification_message_failed(self, online_app, to_deploy_app, e):
        app_name = get_app_friendly_name(online_app)
        notif = "Blue/green preparation failed for [{0}] between [{1}] and [{2}]: {3}".format(app_name, online_app['_id'], to_deploy_app['_id'], str(e))
        return _red(notif)

    def _get_notification_message_aborted(self, app, msg):
        notif = "Blue/green preparation aborted for [{0}] : {1}".format(get_app_friendly_name(app), msg)
        return _yellow(notif)

    def _get_notification_message_done(self, online_app, as_old, as_new, elb_name, elb_dns):
        app_name = get_app_friendly_name(online_app)
        notif = "Blue/green preparation done for [{0}] between [{1}] and [{2}] on ELB '{3}' ({4})".format(app_name, as_old, as_new, elb_name, elb_dns)
        return _green(notif)

    def execute(self):
        """Execute all checks and preparations."""
        log(_green("STATE: Started"), self._log_file)


        online_app, offline_app = get_blue_green_apps(self._app,
                                                      self._worker._db.apps)

        # Check if app has blue green enabled, if is not online
        if not online_app:
            self._worker.update_status("aborted", message=self._get_notification_message_aborted(self._app, "Blue/green is not enabled on this app or not well configured"))
            return

        # Check if app has AS
        # Check if app has up to date AMI
        # Check if all module have been deployed
        # Check if instances are already running
        # Create the testing ELB : {uid}-{app-name}-{env}-{role}-bluegreen, duplicated from the PROD ELB
        # Update auto scale : attach testing ELB, update LaunchConfig, update AS value (duplicate from PROD/online AS)
        # Return / print Testing ELB url/dns
        self._worker.update_status("done", message="DUMMY: [{0}]".format(self._app['name']))
