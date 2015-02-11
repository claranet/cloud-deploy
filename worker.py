from subprocess import call
import datetime
import logging
from settings import MONGO_DBNAME
from boto import sns
from boto.ec2 import autoscale
from redis import Redis
from rq import get_current_job, Connection
from pymongo import MongoClient
from bson.objectid import ObjectId
from pprint import pprint
from notification import Notification

LOG_PATH='/var/log/ghost'
ROOT_PATH=os.path.dirname(os.path.realpath(__file__))
MAIL_LOG_FROM='no-reply@morea.fr'

class Worker:
    _config = None
    _worker_job = None
    _job = None
    _db = None
    _log_file = None
    _app = None

    def __init__(self, dry_run=False):
        self._dry_run = dry_run

    def _log(self, message):
        self._log_file.write("{message}\n".format(message=message))


    def _connect_db(self):
        self._db = MongoClient()[MONGO_DBNAME]


    def _disconnect_db(self):
        MongoClient().disconnect()


    def _update_progress(self, message, **kwargs):
        self._worker_job.meta['progress_message'] = message
        if kwargs and kwargs['percent']:
            self._worker_job.meta['progress_completion'] = kwargs['percent']
        self._worker_job.save()


    def _update_task(self, task_status, message=None):
        self._task['status'] = task_status
        if message:
            self._task['message'] = message
        self._db.tasks.update({ '_id': self._task['_id']}, {'$set': {'status': task_status, 'message': message, 'updated_at': datetime.datetime.now()}})


    def _init_log_file(self):
        self._log_file = open("{log_path}/{job_id}".format(log_path=LOG_PATH, job_id=self._worker_job.id), 'a', 1)


    def _close_log_file(self):
        self._log_file.close()


    def _format_notif(self):
        title = "App: {app_name} - {action} : {status}".format(app_name=self._app['app'], action=self._task['action'], status=self._task['status'])
        message = "Application: {app_name}\nEnvironment: {env}\nAction: {action}\nStatus: {status}".format(env=self._app['env'], app_name=self._app['app'], action=self._task['action'], status=self._task['status'])
        if 'error_message' in self._task.keys():
            message = "{message}\nError: {error_message}".format(message=message, error_message=self._task['error_message'])
        return title, message


    def _mail_log_action(self):
        ses_settings = self._config['ses_settings']
        notif = Notification(aws_access_key=ses_settings['aws_access_key'], aws_secret_key=ses_settings['aws_secret_key'], region=ses_settings['region'])
        subject, body = self._format_notif()
        log = "{log_path}/{job_id}".format(log_path=LOG_PATH, job_id=self._worker_job.id)
        for mail in self._app['log_notifications']:
            notif.send_mail(From=MAIL_LOG_FROM, To=mail, subject=subject, body=body, attachments=[log])


    def execute(self, job_id):
        with Connection():
            self._worker_job = get_current_job()
        self._connect_db()
        self._job = self._db.jobs.find_one({'_id': ObjectId(job_id)})
        self._app = self._db.apps.find_one({'_id': ObjectId(self._job['app_id'])})
        self._init_log_file()
        #FIXME INTROSPECTION ie: commands/deploy Deploy
        result = func(*args, **kwargs)
        self._close_log_file()
        self._mail_log_action()
        self._disconnect_db()


# task_init_app()
if __name__ == '__main__':
    # task_init_app()
    # task_deploy_app(branch="staging")
    # task_predeploy_app()
    print("Yeah !!!")

