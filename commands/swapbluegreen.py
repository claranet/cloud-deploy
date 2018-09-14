import time
import os

from fabric.colors import green as _green, yellow as _yellow, red as _red
from ghost_log import log
from ghost_tools import get_aws_connection_data, get_app_friendly_name, GCallException, get_running_jobs
from ghost_tools import b64decode_utf8, get_ghost_env_variables, gcall
from libs import load_balancing
from libs.deploy import get_path_from_app_with_color
from settings import cloud_connections, DEFAULT_PROVIDER

from ghost_aws import check_autoscale_exists, get_autoscaling_group_and_processes_to_suspend
from ghost_aws import suspend_autoscaling_group_processes, resume_autoscaling_group_processes
from libs.blue_green import get_blue_green_apps, check_app_manifest, get_blue_green_config, abort_if_other_bluegreen_job
from libs.blue_green import ghost_has_blue_green_enabled, get_blue_green_from_app

COMMAND_DESCRIPTION = "Swap the Blue/Green env"
RELATED_APP_FIELDS = ['blue_green']


def is_available(app_context=None):
    ghost_has_blue_green = ghost_has_blue_green_enabled()
    if not ghost_has_blue_green:
        return False
    if not app_context:
        return True
    app_blue_green, app_color = get_blue_green_from_app(app_context)
    return app_blue_green is not None and app_color is not None


class Swapbluegreen(object):
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
    def _get_notification_message_failed(online_app, to_deploy_app, msg):
        app_name = get_app_friendly_name(online_app)
        notif = "Blue/green swap failed for [{0}] between [{1}] and [{2}]: {3}".format(
            app_name, online_app['_id'], to_deploy_app['_id'], msg)
        return _red(notif)

    @staticmethod
    def _get_notification_message_aborted(app, msg):
        notif = "Blue/green swap aborted for [{0}] : {1}".format(get_app_friendly_name(app), msg)
        return _yellow(notif)

    @staticmethod
    def _get_notification_message_done(online_app, as_old, as_new, elb_name, elb_dns):
        app_name = get_app_friendly_name(online_app)
        notif = "Blue/green swap done for [{0}] between [{1}] and [{2}] on ELB '{3}' ({4})".format(
            app_name, as_old, as_new, elb_name, elb_dns)
        return _green(notif)

    @staticmethod
    def _execute_swap_hook(online_app, to_deploy_app, script_name, script_message, log_file):
        for status, app in (('active', online_app), ('inactive', to_deploy_app)):
            script = app.get('blue_green', {}).get('hooks', {}).get(script_name, None)
            if script:
                script_path = os.path.join(get_path_from_app_with_color(app), script_name)
                with open(script_path, 'w') as f:
                    f.write(b64decode_utf8(script))

                script_env = os.environ.copy()
                script_env.update(get_ghost_env_variables(app))

                gcall('bash {}'.format(script_path),
                      '{}: Execute'.format(script_message.format(status=status)),
                      log_file,
                      env=script_env)

    def _update_app_is_online(self, app, is_online):
        """
        Updates the App DB object to set the 'is_online' attribute.
        This attribute should be at True when the ASG is mapped with the online ELB.
        """
        app['blue_green']["is_online"] = is_online
        self._worker._db.apps.update({'_id': app['_id']}, {'$set': {'blue_green.is_online': is_online}})
        log("'{0}' has been set '{1}' for blue/green".format(app['_id'], 'online' if is_online else 'offline'),
            self._log_file)

    def _wait_draining_connection(self, lb_mgr, elb_names):
        """ Wait until the connection draining is reached.

            elb_conn    boto2 obj   Connection object to the ELB endpoint.
            elb_names    List        A list of ELB names.
            Return      None
        """
        wait_before_swap = int(lb_mgr.get_lbs_max_connection_draining_value(elb_names)) + 1
        log(_green('Waiting {0}s: The ELB connection draining time'.format(wait_before_swap)), self._log_file)
        time.sleep(wait_before_swap)

    def _wait_until_instances_registered(self, lb_mgr, elb_names, timeout):
        """ Wait until each instances become online in the Load Balancer.
            If timeout value is reached, raise an exception

            :param   lb_mgr:    load_balacing.LoadBalancerManager:   LB manager
            :param   elb_names:   list        A list of ELB names.
            :param   timeout:     int         Maximum time to wait before the instances become healthy.
            :returns bool:       False if timeout exceeded, True otherwise
        """
        t = 0
        while len(
                [i for i in lb_mgr.get_instances_status_from_lbs(elb_names).values() if 'outofservice' in i.values()]):
            if t > timeout:
                return False
            log(_yellow('Waiting 10s because the instance is not in service in the ELB'), self._log_file)
            time.sleep(10)
            t += 10
        return True

    def _swap_asg(self, lb_mgr, swap_execution_strategy, online_app, to_deploy_app, log_file):
        """ Swap group of instances from A to B atatched to the main ELB

        :param  swap_execution_strategy: string: The swap strategy which can be 'isolated' or 'overlap'
        :param  online_app: object: Ghost app - ASG instances to de-register
        :param  to_deploy_app: object: Ghost app - ASG instances to register
        :param  log_file: str:
        :return tuple (Main ELB name, Main ELB dns)
        """
        app_region = self._app['region']
        as_conn3 = self._cloud_connection.get_connection(app_region, ['autoscaling'], boto_version='boto3')

        # Retrieve autoscaling infos, if any
        as_group_old, as_group_old_processes_to_suspend = get_autoscaling_group_and_processes_to_suspend(
            as_conn3, online_app, log_file)
        as_group_new, as_group_new_processes_to_suspend = get_autoscaling_group_and_processes_to_suspend(
            as_conn3, to_deploy_app, log_file)
        # Retrieve ELB instances
        elb_online_instances = lb_mgr.get_instances_status_from_autoscale(online_app['autoscale']['name'], log_file)
        log(_green('Online configuration : {0}'.format(str(elb_online_instances))), self._log_file)
        elb_tempwarm_instances = lb_mgr.get_instances_status_from_autoscale(to_deploy_app['autoscale']['name'],
                                                                            log_file)
        log(_green('Offline configuration : {0}'.format(str(elb_tempwarm_instances))), self._log_file)

        elb_online, health_check_config = (None, None)
        try:
            log("Swapping using strategy '{0}'".format(swap_execution_strategy), self._log_file)

            # Suspend autoscaling groups
            suspend_autoscaling_group_processes(as_conn3, as_group_old, as_group_old_processes_to_suspend, log_file)
            suspend_autoscaling_group_processes(as_conn3, as_group_new, as_group_new_processes_to_suspend, log_file)

            # Retrieve online ELB object
            elb_online = lb_mgr.get_by_name(elb_online_instances.keys()[0])
            health_check_config = lb_mgr.get_health_check(elb_online.name)

            log(_green('Changing HealthCheck to be "minimal" on online ELB "{0}"'.format(elb_online)), self._log_file)
            lb_mgr.configure_health_check(
                elb_online.name,
                interval=get_blue_green_config(self._config, 'swapbluegreen', 'healthcheck_interval', 5),
                timeout=get_blue_green_config(self._config, 'swapbluegreen', 'healthcheck_timeout', 2),
                healthy_threshold=get_blue_green_config(self._config, 'swapbluegreen',
                                                        'healthcheck_healthy_threshold', 2)
                )
            if swap_execution_strategy == 'isolated':
                log(_green(
                    'De-register all online instances from ELB {0}'.format(', '.join(elb_online_instances.keys()))),
                    self._log_file)
                lb_mgr.deregister_all_instances_from_lbs(elb_online_instances, self._log_file)
                self._wait_draining_connection(lb_mgr, elb_online_instances.keys())
                log(_green('Register and put online new instances to online ELB {0}'.format(
                    ', '.join(elb_online_instances.keys()))), self._log_file)
                lb_mgr.register_all_instances_to_lbs(elb_online_instances.keys(), elb_tempwarm_instances,
                                                     self._log_file)
            elif swap_execution_strategy == 'overlap':
                log(_green('De-register old instances from ELB {0}'.format(', '.join(elb_online_instances.keys()))),
                    self._log_file)
                lb_mgr.deregister_all_instances_from_lbs(elb_online_instances, self._log_file)
                log(_green('Register new instances in the ELB: {0}'.format(elb_online['LoadBalancerName'])),
                    self._log_file)
                lb_mgr.register_all_instances_to_lbs(elb_online_instances.keys(), elb_tempwarm_instances,
                                                     self._log_file)
            else:
                log("Invalid swap execution strategy selected : '{0}'. "
                    "Please choose between 'isolated' and 'overlap'".format(swap_execution_strategy), self._log_file)
                return None, None

            if not self._wait_until_instances_registered(
                    lb_mgr, elb_online_instances.keys(),
                    get_blue_green_config(self._config, 'swapbluegreen', 'registreation_timeout', 45)):
                log(_red("Timeout reached while waiting the instances registration. Rollback process launch"),
                    self._log_file)
                lb_mgr.deregister_instances_from_lbs(elb_online_instances.keys(),
                                                     elb_tempwarm_instances[elb_tempwarm_instances.keys()[0]].keys(),
                                                     self._log_file)
                lb_mgr.register_all_instances_to_lbs(elb_online_instances.keys(), elb_online_instances, self._log_file)
                lb_mgr.register_all_instances_to_lbs(elb_tempwarm_instances.keys(), elb_tempwarm_instances,
                                                     self._log_file)
                log(_yellow("Rollback completed."), self._log_file)
                return None, None

            log(_green(
                'De-register all instances from temp (warm) ELB {0}'.format(', '.join(elb_tempwarm_instances.keys()))),
                self._log_file)
            lb_mgr.deregister_all_instances_from_lbs(elb_tempwarm_instances, self._log_file)

            log(_green('Register old instances to Temp ELB {0} (usefull for another Rollback Swap)'.format(
                ', '.join(elb_tempwarm_instances.keys()))), self._log_file)
            lb_mgr.register_all_instances_to_lbs(elb_tempwarm_instances.keys(), elb_online_instances, self._log_file)

            log(_green('Update autoscale groups with their new ELB'), self._log_file)
            lb_mgr.register_lbs_into_autoscale(to_deploy_app['autoscale']['name'], elb_tempwarm_instances.keys(),
                                               elb_online_instances.keys(), self._log_file)
            lb_mgr.register_lbs_into_autoscale(online_app['autoscale']['name'], elb_online_instances.keys(),
                                               elb_tempwarm_instances.keys(), self._log_file)

            # Update _is_online field in DB on both app
            self._update_app_is_online(online_app, False)  # no more online anymore
            self._update_app_is_online(to_deploy_app, True)  # promotion !

            online_elb_name = elb_online_instances.keys()[0]
            return str(online_elb_name), lb_mgr.get_dns_name(online_elb_name)
        finally:
            if elb_online and health_check_config:
                log(_green(
                    'Restoring original HealthCheck config on online ELB "{0}"'.format(elb_online['LoadBalancerName'])),
                    self._log_file)
                lb_mgr.configure_health_check(elb_online['LoadBalancerName'], **health_check_config)
            resume_autoscaling_group_processes(as_conn3, as_group_old, as_group_old_processes_to_suspend, log_file)
            resume_autoscaling_group_processes(as_conn3, as_group_new, as_group_new_processes_to_suspend, log_file)

    def execute(self):
        log(_green("STATE: Started"), self._log_file)
        swap_execution_strategy = (
            self._job['options'][0] if 'options' in self._job and len(self._job['options']) > 0 else "isolated")
        online_app, to_deploy_app = get_blue_green_apps(
            self._app, self._worker._db.apps, self._log_file)
        if not online_app:
            self._worker.update_status(
                "aborted",
                message=self._get_notification_message_aborted(
                    self._app, "Blue/green is not enabled on this app or not well configured"))
            return

        running_jobs = get_running_jobs(self._db, online_app['_id'], to_deploy_app['_id'], self._job['_id'])
        if abort_if_other_bluegreen_job(
                running_jobs,
                self._worker,
                self._get_notification_message_aborted(
                    self._app,
                    "Please wait until the end of the current jobs before triggering a Blue/green operation"),
                self._log_file):
            return

        try:
            lb_mgr = load_balancing.get_lb_manager(
                self._cloud_connection, self._app['region'], online_app["safe-deployment"]["load_balancer_type"])

            # Check AMI
            if 'ami' not in to_deploy_app:
                self._worker.update_status(
                    "aborted",
                    message=self._get_notification_message_aborted(to_deploy_app, "Please run `Buildimage` first"))
                return
            # Check if modules have been deployed
            if not check_app_manifest(to_deploy_app, self._config, self._log_file, get_path_from_app_with_color(to_deploy_app)):
                self._worker.update_status(
                    "aborted",
                    message=self._get_notification_message_aborted(to_deploy_app, "Please deploy your app's modules"))
                return
            # Check ASG
            if to_deploy_app['autoscale']['name'] and online_app['autoscale']['name']:
                if not (check_autoscale_exists(self._cloud_connection,
                                               to_deploy_app['autoscale']['name'],
                                               to_deploy_app['region'])
                        and check_autoscale_exists(self._cloud_connection,
                                                   online_app['autoscale']['name'],
                                                   online_app['region'])):
                    self._worker.update_status(
                        "aborted",
                        message=self._get_notification_message_aborted(
                            to_deploy_app, "Please set an AutoScale on both green and blue app"))
                    return
            else:
                self._worker.update_status(
                    "aborted",
                    message=self._get_notification_message_aborted(
                        to_deploy_app, "Please set an AutoScale on both green and blue app."))
                return

            # Check if we have two different AS !
            if to_deploy_app['autoscale']['name'] == online_app['autoscale']['name']:
                self._worker.update_status(
                    "aborted",
                    message=self._get_notification_message_aborted(
                        to_deploy_app, "Please set a different AutoScale on green and blue app."))
                return

            # Check if we're ready to swap. If an instance is out of service
            # into the ELB pool raise an exception
            elb_instances = lb_mgr.get_instances_status_from_autoscale(to_deploy_app['autoscale']['name'],
                                                                       self._log_file)
            if len(elb_instances) == 0:
                self._worker.update_status(
                    "aborted",
                    message=self._get_notification_message_aborted(
                        to_deploy_app,
                        "The offline application [{0}] doesn't have a valid Load Balancer associated.'".format(
                            to_deploy_app['_id'])))
                return
            for e in elb_instances.values():
                if len(e.values()) == 0:
                    self._worker.update_status(
                        "aborted",
                        message=self._get_notification_message_aborted(
                            to_deploy_app,
                            "An ELB of the offline application [{0}] has no instances associated.'".format(
                                to_deploy_app['_id'])))
                    return

            if len([i for i in elb_instances.values() if 'outofservice' in i.values()]):
                raise GCallException(
                    'Cannot continue because one or more instances are in the out of service state in the temp ELB')
            else:
                log(_green("AutoScale blue [{0}] and green [{1}] ready for swap".format(
                    online_app['autoscale']['name'], to_deploy_app['autoscale']['name'])), self._log_file)

            self._execute_swap_hook(online_app, to_deploy_app,
                                    'pre_swap', 'Pre swap script for current {status} application',
                                    self._log_file)

            # Swap !
            elb_name, elb_dns = self._swap_asg(lb_mgr, swap_execution_strategy, online_app, to_deploy_app,
                                               self._log_file)
            if not elb_name:
                self._worker.update_status(
                    "failed",
                    message=self._get_notification_message_failed(
                        online_app, to_deploy_app, 'Unable to make blue-green swap'))
                return

            self._execute_swap_hook(online_app, to_deploy_app,
                                    'post_swap', 'Post swap script for previously {status} application',
                                    self._log_file)

            # All good
            done_notif = self._get_notification_message_done(
                online_app, online_app['autoscale']['name'], to_deploy_app['autoscale']['name'], elb_name, elb_dns)
            self._worker.update_status("done", message=done_notif)
        except GCallException as e:
            self._worker.update_status(
                "failed",
                message=self._get_notification_message_failed(online_app, to_deploy_app, str(e)))
