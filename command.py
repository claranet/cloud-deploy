from datetime import datetime
import os
import sys
import traceback
import yaml

from rq import get_current_job, Connection
from pymongo import MongoClient
from bson.objectid import ObjectId

from ghost_log import log

from notification import Notification
from settings import MONGO_DBNAME

LOG_ROOT='/var/log/ghost'
ROOT_PATH=os.path.dirname(os.path.realpath(__file__))
MAIL_LOG_FROM='no-reply@morea.fr'

def format_notif(app, job):
    """
    Returns a formatted title and message couple

    >>> app = {'name': 'myapp', 'env': 'preprod'}
    >>> job = {'command': 'deploy', 'user': 'john', '_created': '2015-06-10 17:09:38', 'status': 'done', 'message': 'Deployment OK: [mymodule]'}
    >>> title, message = format_notif(app, job)
    >>> title
    '[GHOST] App myapp (preprod) - deploy: done (Deployment OK: [mymodule])'
    >>> message
    'Application: myapp\\nEnvironment: preprod\\nAction: deploy\\nStarted: 2015-06-10 17:09:38\\nStatus: done\\nUser: john\\nMessage: Deployment OK: [mymodule]'
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
    return title, message

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
        self._db = MongoClient()[MONGO_DBNAME]


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

    def _init_log_file(self):
        log_path = "{log_path}/{job_id}.txt".format(log_path=LOG_ROOT, job_id=self._worker_job.id)

        # As this method is only supposed to be called in forked rqworker process,
        # it is safe to redirect sys.stdout and sys.stderr to the job's log file.
        # This is mainly needed to capture all fabric & paramiko outputs,
        # but may also serve in other cases.
        sys.stdout = sys.stderr = self.log_file = open(log_path, 'a', 1)

        self._db.jobs.update({ '_id': self.job['_id']}, {'$set': {'log_id': self._worker_job.id }})

    def _close_log_file(self):
        self.log_file.close()


    def _mail_log_action(self):
        ses_settings = self._config['ses_settings']
        notif = Notification(aws_access_key=ses_settings['aws_access_key'], aws_secret_key=ses_settings['aws_secret_key'], region=ses_settings['region'])
        subject, body = format_notif(self.app, self.job)
        log = "{log_path}/{job_id}.txt".format(log_path=LOG_ROOT, job_id=self._worker_job.id)
        log_stat = os.stat(log)
        if log_stat.st_size > 512000:
            os.system('gzip -k '+log)
            log = log+'.gz'
        for mail in self.app['log_notifications']:
            notif.send_mail(From=MAIL_LOG_FROM, To=mail, subject=subject, body=body, attachments=[log])
            pass


    def execute(self, job_id):
        with Connection():
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
            self._close_log_file()
            self._mail_log_action()
            self._disconnect_db()

