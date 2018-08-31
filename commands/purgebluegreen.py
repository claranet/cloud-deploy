from fabric.colors import green as _green, yellow as _yellow, red as _red

from ghost_log import log
from ghost_tools import get_aws_connection_data, get_app_friendly_name, GCallException, boolify, get_running_jobs
from libs import load_balancing
from settings import cloud_connections, DEFAULT_PROVIDER

from ghost_aws import check_autoscale_exists, get_autoscaling_group_and_processes_to_suspend
from ghost_aws import suspend_autoscaling_group_processes, resume_autoscaling_group_processes
from libs.autoscaling import get_instances_from_autoscaling, flush_instances_update_autoscale
from libs.blue_green import get_blue_green_apps
from libs.blue_green import abort_if_other_bluegreen_job
from libs.blue_green import ghost_has_blue_green_enabled, get_blue_green_from_app

COMMAND_DESCRIPTION = "Purge the Blue/Green env"
RELATED_APP_FIELDS = ['blue_green']


def is_available(app_context=None):
    ghost_has_blue_green = ghost_has_blue_green_enabled()
    if not ghost_has_blue_green:
        return False
    if not app_context:
        return True
    app_blue_green, app_color = get_blue_green_from_app(app_context)
    return app_blue_green is not None and app_color is not None


class Purgebluegreen(object):
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
            self._config,
            **self._connection_data
        )

    @staticmethod
    def _get_notification_message_failed(app, msg):
        notif = "Blue/green purge failed for [{0}] : {1}".format(get_app_friendly_name(app), msg)
        return _red(notif)

    @staticmethod
    def _get_notification_message_aborted(app, msg):
        notif = "Blue/green purge aborted for [{0}] : {1}".format(get_app_friendly_name(app), msg)
        return _yellow(notif)

    @staticmethod
    def _get_notification_message_done(app):
        notif = "Blue/green purge done for [{0}] [{1}]".format(get_app_friendly_name(app), app['_id'])
        return _green(notif)

    def _update_app_autoscale_options(self, app, log_file):
        """ Updates the App DB object to set the 'autoscale' attribute.
        """
        self._worker._db.apps.update({'_id': app['_id']}, {'$set': {
            'autoscale.min': 0,
            'autoscale.max': 0,
            'autoscale.current': 0
        }})
        log(_green("'{0}' autoscale has been update '{1}'".format(app['_id'], app['autoscale']['name'])), log_file)

    def execute(self):
        log(_green("STATE: Started"), self._log_file)

        online_app, offline_app = get_blue_green_apps(self._app,
                                                      self._worker._db.apps,
                                                      self._log_file)
        if not offline_app:
            self._worker.update_status(
                "aborted",
                message=self._get_notification_message_aborted(
                    self._app, "Blue/green is not enabled on this app or not well configured"))
            return

        running_jobs = get_running_jobs(self._db, online_app['_id'], offline_app['_id'], self._job['_id'])
        if abort_if_other_bluegreen_job(
                running_jobs,
                self._worker,
                self._get_notification_message_aborted(
                    self._app,
                    "Please wait until the end of the current jobs before triggering a Blue/green operation"),
                self._log_file):
            return

        # Check ASG
        if offline_app['autoscale']['name'] and online_app['autoscale']['name']:
            if not (
                        check_autoscale_exists(self._cloud_connection, offline_app['autoscale']['name'],
                                               offline_app['region'])
                    and check_autoscale_exists(self._cloud_connection, online_app['autoscale']['name'],
                                               online_app['region'])):
                self._worker.update_status(
                    "aborted",
                    message=self._get_notification_message_aborted(
                        offline_app, "Not AutoScale group found on the offline app to purge."))
                return
        else:
            self._worker.update_status(
                "aborted",
                message=self._get_notification_message_aborted(
                    offline_app, "Not AutoScale group found on the offline app to purge."))
            return

        # Check if we have two different AS !
        if offline_app['autoscale']['name'] == online_app['autoscale']['name']:
            self._worker.update_status(
                "aborted",
                message=self._get_notification_message_aborted(
                    offline_app, "Please set a different AutoScale on green and blue app."))
            return

        # Retrieve autoscaling infos, if any
        app_region = offline_app['region']
        as_conn3 = self._cloud_connection.get_connection(app_region, ['autoscaling'], boto_version='boto3')
        as_group, as_group_processes_to_suspend = get_autoscaling_group_and_processes_to_suspend(
            as_conn3, offline_app, self._log_file)
        suspend_autoscaling_group_processes(as_conn3, as_group, as_group_processes_to_suspend, self._log_file)

        try:
            lb_mgr = load_balancing.get_lb_manager(
                self._cloud_connection, self._app['region'], online_app["safe-deployment"]["load_balancer_type"])

            # Check if instances are running
            if not get_instances_from_autoscaling(offline_app['autoscale']['name'], as_conn3):
                log(_yellow(
                    " WARNING: Autoscaling Group [{0}] of offline app is empty. "
                    "No running instances to clean detected.".format(offline_app['autoscale']['name'])),
                    self._log_file)

            temp_elb_names = lb_mgr.list_lbs_from_autoscale(offline_app['autoscale']['name'], self._log_file,
                                                       {'bluegreen-temporary': 'true'})

            if len(temp_elb_names) > 1:
                self._worker.update_status(
                    "aborted",
                    message=self._get_notification_message_aborted(
                        offline_app, "There are more than one temporary ELB associated to the ASG '{0}' \n"
                                     "ELB found: {1}".format(
                                        offline_app['autoscale']['name'],
                                        str(temp_elb_names))))
                return

            # Detach temp ELB from ASG
            log(_green("Detach the current temporary ELB [{0}] from the AutoScale [{1}]".format(
                temp_elb_names, offline_app['autoscale']['name'])), self._log_file)
            lb_mgr.register_lbs_into_autoscale(offline_app['autoscale']['name'], temp_elb_names, None, self._log_file)

            # Update ASG and kill instances
            log("Update AutoScale with `0` on mix, max, desired values.", self._log_file)
            log(_yellow("Destroy all instances in the AutoScale and all instances matching the `app_id` [{0}]".format(
                offline_app['_id'])), self._log_file)
            flush_instances_update_autoscale(as_conn3, self._cloud_connection, offline_app, self._log_file)

            # Destroy temp ELB
            if temp_elb_names:
                lb_mgr.destroy_lb(temp_elb_names[0], self._log_file)
            else:
                log(" INFO: No ELB to destroy", self._log_file)

            # Update App Autoscale values, next buildimage or updateautoscaling should not set values different from 0
            self._update_app_autoscale_options(offline_app, self._log_file)

            # All good
            self._worker.update_status("done", message=self._get_notification_message_done(offline_app))
        except GCallException as e:
            self._worker.update_status("failed", message=self._get_notification_message_failed(offline_app, str(e)))
        finally:
            # Resume autoscaling groups in any case
            resume_autoscaling_group_processes(as_conn3, as_group, as_group_processes_to_suspend, self._log_file)
