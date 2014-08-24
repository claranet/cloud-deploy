import functools
from subprocess import call
import datetime
import os
import shutil
import tempfile
import logging
from boto import sns
from boto.ec2 import autoscale
from redis import Redis
from rq import Queue
from rq import get_current_job
from pymongo import MongoClient
from notification import Notification

LOG_PATH='/var/log/ghost'
ROOT_PATH=os.path.dirname(os.path.realpath(__file__))
MAIL_LOG_FROM='no-reply@morea.fr'


class CallException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def prepare_task(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        args[0]._job = get_current_job()
        args[0]._connect_db()
        args[0]._config = args[0]._db.config.find_one()
        args[0]._init_log_file()
        args[0]._task = \
                {
                        'app_id': args[0]._app['_id'],
                        'action': func.__name__,
                        'job_id': args[0]._job.id,
                        'status': 'in_progress',
                        'created_at': datetime.datetime.now()
                }
        args[0]._db.tasks.insert(args[0]._task)
        args[0]._set_git_repo()
        args[0]._set_app_path()
        args[0]._set_autoscale_group()
        try:
            args[0]._update_progress('In Progress', percent=0)
            result = func(*args, **kwargs)
            args[0]._update_progress('Done', percent=100)
            args[0]._update_task('done')
        except CallException, e:
            args[0]._update_progress('Failed', percent=100)
            args[0]._update_task('failed', message=e.message)
        args[0]._close_log_file()
        args[0]._notif_action()
        args[0]._mail_log_action()
        args[0]._disconnect_db()
    return wrapper


class Worker:
    _config = None
    _job = None
    _db = None
    _task = None
    _log_file = None
    _app = None
    _app_path = None
    _git_repo = None
    _dry_run = None
    _as_conn = None
    _as_group = None

    def __init__(self, app, dry_run=False):
        self._app = app
        self._dry_run = dry_run


    def _log(self, message):
        self._log_file.write("{message}\n".format(message=message))


    def _gcall(self, args, cmd_description):
        self._log("CMD: %s" % cmd_description)
        if not self._dry_run:
            ret = call(args, stdout=self._log_file, stderr=self._log_file, shell=True)
            if (ret != 0):
                raise CallException("ERROR: %s" % cmd_description)


    def _predeploy_app(self):
        """
        Execute tasks before packaging application (ie: install lib dependencies)
        """
        predeploy = os.path.join(ROOT_PATH, 'predeploy', 'symfony_predeploy.sh')
        shutil.copy(predeploy, self._app_path)
        os.chdir(self._app_path)
        self._gcall('./symfony_predeploy.sh %s' % self._app['env'], 'Predeploy script')


    def _postdeploy_app(self):
        """
        Execute tasks after deployment (ie: clear cache)
        """
        postdeploy = os.path.join(ROOT_PATH, 'postdeploy', 'symfony_postdeploy.sh')
        shutil.copy(postdeploy, self._app_path)
        os.chdir(self._app_path)
        self._gcall('./symfony_postdeploy.sh %s' % self._app['env'], 'Postdeploy script')


    def _set_as_conn(self):
        self._as_conn = autoscale.connect_to_region(self._app['aws_region'])


    def _set_autoscale_group(self):
        if not self._as_conn:
            self._set_as_conn()
        if 'as_name' in self._app.keys():
            self._as_group = self._as_conn.get_all_groups(names=self._app['as_name'])


    def _start_autoscale(self):
        if (self._as_group):
            self._as_conn.resume_processes(self._as_group)


    def _stop_autoscale(self):
        if (self._as_group):
            self._as_conn.suspend_processes(self._as_group)


    def _sync_instances(self, task_name):
        os.chdir(ROOT_PATH)
        cmd = "/usr/local/bin/fab -i {key_path} set_hosts:ghost_app={app},ghost_env={env},ghost_role={role},region={aws_region} {0}".format(task_name, **self._app)
        self._gcall(cmd, "Updating current instances")


    def _connect_db(self):
        self._db = MongoClient().ghost


    def _disconnect_db(self):
        MongoClient().disconnect()


    def _update_progress(self, message, **kwargs):
        self._job.meta['progress_message'] = message
        if kwargs and kwargs['percent']:
            self._job.meta['progress_completion'] = kwargs['percent']
        self._job.save()


    def _update_status(self, status):
        pass


    def _update_task(self, task_status, message=None):
        self._task['status'] = task_status
        if message:
            self._task['message'] = message
        self._db.tasks.update({ '_id': self._task['_id']}, {'$set': {'status': task_status, 'message': message, 'updated_at': datetime.datetime.now()}})


    def _set_app_path(self):
        self._app_path = os.path.join('/', 'ghost', self._app['app'], self._app['env'], self._app['role'], self._git_repo)


# FIXME: handle incorrect Git repo path with try/except
    def _set_git_repo(self):
        git_repo = self._app['git_repo'].split('/')
        self._git_repo = git_repo[len(git_repo)-1][:-4]


    def _init_log_file(self):
        self._log_file = open("{log_path}/{job_id}".format(log_path=LOG_PATH, job_id=self._job.id), 'a')


    def _close_log_file(self):
        self._log_file.close()


    def _package_app(self):
        os.chdir("/ghost/{app}/{env}/{role}/{0}".format(self._git_repo, **self._app))
        pkg_name = "%s_%s.tar.gz" % (datetime.datetime.now().strftime("%Y%m%d%H%M"), self._git_repo)
        self._gcall("tar cvzf ../%s . > /dev/null" % pkg_name, "Creating package: %s" % pkg_name)
        self._gcall("s3cmd put ../{0} {bucket_s3}/{app}/{env}/{role}/".format(pkg_name, **self._app), "Uploading package: %s" % pkg_name)
        return pkg_name


    def _format_notif(self):
        title = "App: {app_name} - {action} : {status}".format(app_name=self._app['app'], action=self._task['action'], status=self._task['status'])
        message = "Application: {app_name}\nEnvironment: {env}\nAction: {action}\nStatus: {status}".format(env=self._app['env'], app_name=self._app['app'], action=self._task['action'], status=self._task['status'])
        if 'error_message' in self._task.keys():
            message = "{message}\nError: {error_message}".format(message=message, error_message=self._task['error_message'])
        return title, message


    def _notif_action(self):
        title, message = self._format_notif()
        conn = sns.connect_to_region(self._app['aws_region'])
        conn.publish(self._app['notif_arn'], message, title) 


    def _mail_log_action(self):
        ses_settings = self._config['ses_settings']
        notif = Notification(aws_access_key=ses_settings['aws_access_key'], aws_secret_key=ses_settings['aws_secret_key'], region=ses_settings['region'])
        subject, body = self._format_notif()
        log = "{log_path}/{job_id}".format(log_path=LOG_PATH, job_id=self._job.id)
        for mail in self._app['log_notifications']:
            notif.send_mail(From=MAIL_LOG_FROM, To=mail, subject=subject, body=body, attachments=[log])


    def _purge_package(self, pkg_name):
        task_name = "purge:{0}".format(pkg_name)
        self._gcall("/usr/local/bin/fab -i {key_path} set_hosts:ghost_app={app},ghost_env={env},ghost_role={role},region={aws_region} {0}".format(task_name, **self._app), "Purging package: %s" % pkg_name)


    @prepare_task
    def init_app(self, options={}):
        os.chdir("/ghost")
        try:
            os.makedirs("{app}/{env}/{role}".format(**self._app))
        except:
            raise CallException("Init app, creating directory")
        os.chdir("/ghost/{app}/{env}/{role}".format(**self._app))
        self._gcall("git clone https://{git_login}:{git_password}@{git_repo}".format(**self._app), "Git clone")
        os.chdir(self._git_repo)


    @prepare_task
    def deploy_app(self, commit=None):
        """
        0) Update sourcecode
        1) Stop Autoscaling
        2) Update MANIFEST on S3
        3) Deploy package on Running EC2 instances
        4) Restart Webserver
        5) Start Autoscaling
        """
        os.chdir(self._app_path)
        self._gcall("git pull", "Git pull")
        self._gcall("git checkout %s" % commit, "Git checkout: %s" % commit)
        self._predeploy_app()
        pkg_name = self._package_app()
        manifest, manifest_path = tempfile.mkstemp()
        os.write(manifest, "%s" % pkg_name)
        self._set_as_conn()
        self._stop_autoscale()
        self._gcall("s3cmd put {0} {bucket_s3}/{app}/{env}/{role}/MANIFEST".format(manifest_path, **self._app), "Upload manifest")
        self._sync_instances('deploy')
        os.close(manifest)
        self._start_autoscale()
        self._db.apps.update({'_id': self._app['_id']}, { '$push': {'deploy': pkg_name} })
        self._app = self._db.apps.find_one({'_id': self._app['_id']})
        if len(self._app['deploy']) > 3:
            self._purge_package(self._app['deploy'][0])
            self._db.apps.update({'_id': self._app['_id']}, { '$pop': {'deploy': -1} })


    @prepare_task
    def execute(self, command=""):
        os.chdir(self._app_path)
        self._gcall(command, command)


# task_init_app()
if __name__ == '__main__':
    # task_init_app()
    # task_deploy_app(branch="staging")
    # task_predeploy_app()
    print("Yeah !!!")

