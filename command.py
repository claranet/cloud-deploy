from datetime import datetime
import os
import sys
import traceback
import yaml
import gzip
import shutil
import traceback
import logging
from sh import head, tail

from redis import Redis
from rq import get_current_job, Connection
from pymongo import MongoClient
from bson.objectid import ObjectId

from ghost_log import log
from ghost_tools import get_job_log_remote_path
from ghost_aws import push_file_to_s3

from notification import Notification
from settings import cloud_connections, DEFAULT_PROVIDER
from settings import MONGO_DBNAME, MONGO_HOST, MONGO_PORT, REDIS_HOST

LOG_ROOT='/var/log/ghost'
ROOT_PATH=os.path.dirname(os.path.realpath(__file__))
MAIL_LOG_FROM_DEFAULT='no-reply@morea.fr'

def format_html_mail_body(app, job):
    """
    Returns a formatted HTML mail body content
    """
    html_template = """
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<style type="text/css">
td{{font-family:arial,helvetica,sans-serif;}}
</style>

<p><span style="font-size:28px"><span style="color:#000; font-family:arial,helvetica,sans-serif">Ghost job triggered by </span><strong>{user}</strong></span></p>

<table border="0" cellpadding="1" cellspacing="1" style="font-family:arial,helvetica,sans-serif; height:231px; width:700px">
    <tbody>
        <tr>
            <td style="background-color:#858585"><span style="font-size:14px"><strong><span style="color:rgb(255, 255, 255)">Status</span></strong></span></td>
            <td style="background-color:{status_color}"><strong><span style="color:rgb(255, 255, 255)">{status}</span></strong></td>
        </tr>
        <tr>
            <td style="background-color:#858585"><span style="font-size:14px"><strong><span style="color:rgb(255, 255, 255)">Application</span></strong></span></td>
            <td style="background-color:#d1d6da">{app}</td>
        </tr>
        <tr>
            <td style="background-color:#858585"><span style="font-size:14px"><strong><span style="color:rgb(255, 255, 255)">Environment</span></strong></span></td>
            <td style="background-color:#d1d6da">{env}</td>
        </tr>
        <tr>
            <td style="background-color:#858585"><span style="font-size:14px"><strong><span style="color:rgb(255, 255, 255)">Role</span></strong></span></td>
            <td style="background-color:#d1d6da">{role}</td>
        </tr>
        <tr>
            <td style="background-color:#858585"><span style="font-size:14px"><strong><span style="color:rgb(255, 255, 255)">Command</span></strong></span></td>
            <td style="background-color:#d1d6da">{command}</td>
        </tr>
        <tr>
            <td style="background-color:#858585"><span style="font-size:14px"><strong><span style="color:rgb(255, 255, 255)">Job ID</span></strong></span></td>
            <td style="background-color:#d1d6da">{jobId}</td>
        </tr>
        <tr>
            <td style="background-color:#858585"><span style="font-size:14px"><strong><span style="color:rgb(255, 255, 255)">Job message</span></strong></span></td>
            <td style="background-color:#d1d6da"><pre>{message}</pre></td>
        </tr>
        <tr>
            <td style="background-color:#FFFFFF">&nbsp;</td>
            <td style="background-color:#FFFFFF">&nbsp;</td>
        </tr>
        <tr>
            <td style="background-color:#858585"><strong><span style="font-size:14px"><span style="color:rgb(255, 255, 255)">Date</span></span></strong></td>
            <td style="background-color:#d1d6da">
                <table border="0" cellpadding="1" cellspacing="1" style="font-size:14px; height:70px; width:420px">
                    <tbody>
                        <tr>
                            <td><strong>Creation</strong><br>
                            {creation_date}</td>
                            <td><strong>End</strong><br>
                            {end_date}</td>
                        </tr>
                    </tbody>
                </table>
            </td>
        </tr>
    </tbody>
</table>

<table border="0" cellpadding="0" cellspacing="0" style="color:rgb(102, 102, 102); font-family:arial,helvetica,sans-serif; font-size:12px; height:200px; width:700px">
<br>
<br>
</table>
<p></p>
<table cellpadding="1" cellspacing="1" style="height:84px; width:700px">
   <tbody>
         <tr>
             <td width="300"><img src="https://www.cloudeploy.io/ghost/mail_footer_image.png" width="300" height="127"></td>
             <td width="115"><span style="font-family:arial,helvetica,sans-serif"><span style="font-size:12px; color: #333;">&nbsp;</span></span></td>
        </tr>
     </tbody>
</table>
    """

    html_body = html_template.format(
        user = job['user'],
        status = job['status'],
        status_color = 'rgb(218, 0, 26)' if job['status'] == 'failed' else '#00A800',
        app = app['name'],
        env = app['env'],
        role = app['role'],
        command = job['command'],
        jobId = str(job['_id']),
        message = job['message'],
        creation_date = job['_created'],
        end_date = job['_updated'],
    )
    return html_body

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

    def _push_log_to_s3(self):
        cloud_connection = cloud_connections.get(self.app.get('provider', DEFAULT_PROVIDER))(None)
        log_path = self._get_log_path()
        bucket = self._config['bucket_s3']
        region = self._config.get('bucket_region', self.app['region'])
        key_path = get_job_log_remote_path(self._worker_job.id)
        push_file_to_s3(cloud_connection, bucket, region, key_path, log_path)

    def _mail_log_action(self, subject, body):
        ses_settings = self._config['ses_settings']
        notif = Notification(aws_access_key=ses_settings['aws_access_key'], aws_secret_key=ses_settings['aws_secret_key'], region=ses_settings['region'])
        html_body = format_html_mail_body(self.app, self.job)
        log = self._get_log_path()
        log_stat = os.stat(log)
        try:
            if log_stat.st_size > 512000:
                with open(log, 'rb') as f_in, gzip.open(log+'.gz', 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                    log = log+'.gz'
            for mail in self.app['log_notifications']:
                notif.send_mail(From=ses_settings.get('mail_from', MAIL_LOG_FROM_DEFAULT), To=mail, subject=subject, body_text=body, body_html=html_body, attachments=[log])
                pass
        except:
            logging.error("An exception occurred: {}".format(sys.exc_value))
            traceback.print_exc()

    def _slack_notification_action(self, slack_msg):
        log_path = self._get_log_path()
        notif = Notification()
        slack_configs = self._config.get('slack_configs')
        ghost_base_url = self._config.get('ghost_base_url')
        job_log_tail = ''.join(tail('-n', '5', log_path))
        job_log = '[...]\n' + job_log_tail
        if slack_configs and len(slack_configs):
            for slack_conf in slack_configs:
                slack_conf['ghost_base_url'] = ghost_base_url
                notif.send_slack_notification(slack_conf, slack_msg, self.app, self.job, job_log) #, self.log_file) # Log file for debug purpose only


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
            self._push_log_to_s3()
            self._disconnect_db()
