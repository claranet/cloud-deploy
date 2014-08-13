import functools
from subprocess import call
import datetime
import os
import shutil
import tempfile
import logging
from boto import ec2
from redis import Redis
from rq import Queue
from rq import get_current_job
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Task, CDApp


LOG_PATH='/var/log/ghost'
SQLITE_DB_PATH='ghost.db'
ROOT_PATH=os.path.dirname(os.path.realpath(__file__))

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
        args[0]._init_log_file()
        args[0]._task = Task(args[0]._app.id, func.__name__, args[0]._job.id, 'in_progress')
        args[0]._db.add(args[0]._task)
        args[0]._db.commit()
        args[0]._set_git_repo()
        args[0]._set_app_path()
        try:
            args[0]._update_progress('In Progress', percent=0)
            result = func(*args, **kwargs)
            args[0]._update_progress('Done', percent=100)
            args[0]._task.status = 'done'
        except CallException, e:
            args[0]._update_progress('Failed', percent=100)
            args[0]._task.status = 'failed'
        args[0]._close_log_file()
        args[0]._db.commit()
    return wrapper


class Worker:
    _job = None
    _db = None
    _task = None
    _log_file = None
    _app = None
    _app_path = None
    _git_repo = None
    _dry_run = None

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
        self._gcall('./symfony_predeploy.sh %s' % self._app.env, 'Predeploy script')


    def _postdeploy_app(self):
        """
        Execute tasks after deployment (ie: clear cache)
        """
        postdeploy = os.path.join(ROOT_PATH, 'postdeploy', 'symfony_postdeploy.sh')
        shutil.copy(postdeploy, self._app_path)
        os.chdir(self._app_path)
        self._gcall('./symfony_postdeploy.sh %s' % self._app.env, 'Postdeploy script')


    def _search_autoscale(self):
        pass


    def _start_autoscale(self):
        pass


    def _stop_autoscale(self):
        pass


    def _sync_instances(self, task_name):
        os.chdir(ROOT_PATH)
        cmd = "/usr/local/bin/fab -i {app.key_path} set_hosts:ghost_app={app.app},ghost_env={app.env},ghost_role={app.role} {task_name}".format(app=self._app, task_name=task_name)
        self._gcall(cmd, "Updating current instances")


    def _connect_db(self):
        db_path = os.path.join(ROOT_PATH, SQLITE_DB_PATH)
        engine = create_engine('sqlite:///' + db_path, echo=True)
        # create a configured "Session" class
        Session = sessionmaker(bind=engine)
        # create a Session
        session = Session()
        session._model_changes = {}
        self._db = session


    def _update_progress(self, message, **kwargs):
        self._job.meta['progress_message'] = message
        if kwargs and kwargs['percent']:
            self._job.meta['progress_completion'] = kwargs['percent']
        self._job.save()


    def _update_status(self, status):
        pass


    def _set_app_path(self):
        self._app_path = os.path.join('/', 'ghost', self._app.app, self._app.env, self._app.role, self._git_repo)


# FIXME: handle incorrect Git repo path with try/except
    def _set_git_repo(self):
        git_repo = self._app.git_path.split('/')
        self._git_repo = git_repo[len(git_repo)-1][:-4]


    def _init_log_file(self):
        self._log_file = open("{log_path}/{job_id}".format(log_path=LOG_PATH, job_id=self._job.id), 'a')


    def _close_log_file(self):
        self._log_file.close()


    def _package_app(self):
        os.chdir("/ghost/{app.app}/{app.env}/{app.role}/{git_repo}".format(app=self._app, git_repo=self._git_repo))
        pkg_name = "%s_%s.tar.gz" % (datetime.datetime.now().strftime("%Y%m%d%H%M"), self._git_repo)
        self._gcall("tar cvzf ../%s . > /dev/null" % pkg_name, "Creating package: %s" % pkg_name)
        self._gcall("s3cmd put ../{pkg_name} {app.bucket_s3}/{app.app}/{app.env}/{app.role}/".format(pkg_name=pkg_name, app=self._app), "Uploading package: %s" % pkg_name)
        return pkg_name


    @prepare_task
    def init_app(self, options={}):
        os.chdir("/ghost")
        try:
            os.makedirs("{app.app}/{app.env}/{app.role}".format(app=self._app))
        except:
            raise CallException("Init app, creating directory")
        os.chdir("/ghost/{app.app}/{app.env}/{app.role}".format(app=self._app))
        self._gcall("git clone https://{app.git_login}:{app.git_password}@{app.git_path}".format(app=self._app), "Git clone")
        os.chdir(_get_git_repo())


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
        self._stop_autoscale()
        self._gcall("s3cmd put {manifest_path} {app.bucket_s3}/{app.app}/{app.env}/{app.role}/MANIFEST".format(manifest_path=manifest_path, app=self._app), "Upload manifest")
        self._sync_instances('deploy')
        os.close(manifest)
        self._start_autoscale()


# task_init_app()
if __name__ == '__main__':
    # task_init_app()
    # task_deploy_app(branch="staging")
    # task_predeploy_app()
    print("Yeah !!!")

