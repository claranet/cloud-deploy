from datetime import datetime
import os
import sys
import traceback
import yaml
from sh import head, tail

from redis import Redis
from rq import get_current_job, Connection
from pymongo import MongoClient
from bson.objectid import ObjectId

from ghost_log import log

from notification import Notification
from settings import MONGO_DBNAME, MONGO_HOST, MONGO_PORT, REDIS_HOST

LOG_ROOT='/var/log/ghost'
ROOT_PATH=os.path.dirname(os.path.realpath(__file__))
MAIL_LOG_FROM_DEFAULT='no-reply@morea.fr'

def format_notif(app, job):
    """
    Returns a formatted title and message couple

    >>> app = {'name': 'myapp', 'env': 'preprod', 'role': 'webfront'}
    >>> job = {'command': 'deploy', 'user': 'john', '_created': '2015-06-10 17:09:38', 'status': 'done', 'message': 'Deployment OK: [mymodule]'}
    >>> title, message, slack_msg = format_notif(app, job)
    >>> title
    '[GHOST] App myapp (preprod) - deploy: done (Deployment OK: [mymodule])'
    >>> message
    'Application: myapp\\nEnvironment: preprod\\nAction: deploy\\nStarted: 2015-06-10 17:09:38\\nStatus: done\\nUser: john\\nMessage: Deployment OK: [mymodule]'
    >>> slack_msg
    ':ok_hand: [myapp][*preprod*][webfront] *deploy* job triggered by [*john*] is *done* (message: Deployment OK: [mymodule])'
    """
    title_template = "[GHOST] App {app_name} ({app_env}) - {command}: {status} ({message})"
    title = title_template.format(app_name=app['name'],
                                  app_env=app['env'],
                                  command=job['command'],
                                  user=job['user'],
                                  status=job['status'],
                                  message=job['message'])
    message_template = "Application: {app_name}\nEnvironment: {app_env}\nAction: {command}\nStarted: {started}\nStatus: {status}\nUser: {user}\nMessage: {message}"
    message = message_template.format(app_name=app['name'],
                                      app_env=app['env'],
                                      command=job['command'],
                                      started=job['_created'],
                                      user=job['user'],
                                      status=job['status'],
                                      message=job['message'])
    slack_tpl = "{emoji} [{app_name}][*{app_env}*][{app_role}] *{command}* job triggered by [*{user}*] is *{status}* (message: {message})"
    slack_msg = slack_tpl.format(emoji=':warning:' if job['status'] == 'failed' else ':ok_hand:',
                                 app_name=app['name'],
                                 app_env=app['env'],
                                 app_role=app['role'],
                                 command=job['command'],
                                 user=job['user'],
                                 status=job['status'],
                                 message=job['message'])
    return title, message, slack_msg

class Command:
    _config = None
    _worker_job = None
    job = None
    _db = None
    log_file = None
    app = None

    def __init__(self, dry_run=False):
        self._dry_run = dry_run
        rootdir = os.path.dirname(os.path.realpath(__file__))
        conf_file_path = rootdir + "/config.yml"
        conf_file = open(conf_file_path, 'r')
        self._config = yaml.load(conf_file)


    def _connect_db(self):
        self._db = MongoClient(host=MONGO_HOST, port=MONGO_PORT)[MONGO_DBNAME]


    def _disconnect_db(self):
        MongoClient().close()


    #FIXME: not used anymore
    def _update_progress(self, message, **kwargs):
        self._worker_job.meta['progress_message'] = message
        if kwargs and kwargs['percent']:
            self._worker_job.meta['progress_completion'] = kwargs['percent']
        self._worker_job.save()


    def update_status(self, status, message=None):
        self.job['status'] = status
        self.job['message'] = message
        log(message, self.log_file)
        self._db.jobs.update({ '_id': self.job['_id']}, {'$set': {'status': status, 'message': message, '_updated': datetime.now()}})

    def _get_log_path(self):
        log_path = "{log_path}/{job_id}.txt".format(log_path=LOG_ROOT, job_id=self._worker_job.id)
        return log_path

    def _init_log_file(self):
        log_path = self._get_log_path()

        # As this method is only supposed to be called in forked rqworker process,
        # it is safe to redirect sys.stdout and sys.stderr to the job's log file.
        # This is mainly needed to capture all fabric & paramiko outputs,
        # but may also serve in other cases.
        sys.stdout = sys.stderr = self.log_file = open(log_path, 'a', 1)

        self._db.jobs.update({ '_id': self.job['_id']}, {'$set': {'log_id': self._worker_job.id }})

    def _close_log_file(self):
        self.log_file.close()


    def _mail_log_action(self, subject, body):
        ses_settings = self._config['ses_settings']
        notif = Notification(aws_access_key=ses_settings['aws_access_key'], aws_secret_key=ses_settings['aws_secret_key'], region=ses_settings['region'])
        log = "{log_path}/{job_id}.txt".format(log_path=LOG_ROOT, job_id=self._worker_job.id)
        log_stat = os.stat(log)
        if log_stat.st_size > 512000:
            os.system('gzip -k '+log)
            log = log+'.gz'
        for mail in self.app['log_notifications']:
            notif.send_mail(From=ses_settings.get('mail_from', MAIL_LOG_FROM_DEFAULT), To=mail, subject=subject, body=body, attachments=[log])
            pass

    def _slack_notification_action(self, slack_msg):
        log_path = self._get_log_path()
        notif = Notification()
        slack_config = self._config.get('slack_configs')
#        job_log_head = ''.join(head('-n', '10', log_path))
        job_log_tail = ''.join(tail('-n', '5', log_path))
        job_log = '[...]\n' + job_log_tail
        if slack_config:
            notif.send_slack_notification(slack_config, slack_msg, self.app, self.job, job_log) #, self.log_file) # Log file for debug purpose only


    def execute(self, job_id):
        with Connection(Redis(host=REDIS_HOST)):
            self._worker_job = get_current_job()
        self._connect_db()
        self.job = self._db.jobs.find_one({'_id': ObjectId(job_id)})
        self.app = self._db.apps.find_one({'_id': ObjectId(self.job['app_id'])})
        self._init_log_file()
        klass_name = self.job['command'].title()
        mod = __import__('commands.' + self.job['command'], fromlist=[klass_name])
        command = getattr(mod, klass_name)(self)

        # Execute command and always mark the job as 'failed' in case of an unexpected exception
        try:
            if self.job['status'] == 'init':
                self.update_status("started", "Job processing started")
                command.execute()
            else:
                self.update_status("aborted", "Job was already in '{}' status (not in 'init' status)".format(self.job['status']))
        except :
            message = sys.exc_info()[0]
            log(message, self.log_file)
            traceback.print_exc(file=self.log_file)
            self.update_status("failed", str(message))
            raise
        finally:
            subject, body, slack_msg = format_notif(self.app, self.job)
            self._slack_notification_action(slack_msg)
            self._close_log_file()
            self._mail_log_action(subject, body)
            self._disconnect_db()

