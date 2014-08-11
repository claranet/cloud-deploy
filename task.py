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


def gcall(args, cmd_description):
    global log_file
    ret = call(args, stdout=log_file, stderr=log_file, shell=True)
    if (ret != 0):
        raise CallException("ERROR: %s" % cmd_description)


def prepare_task(func):
    @functools.wraps(func)
    def wrapit(*args, **kwargs):
        job = get_current_job()
        db = connect_db()
        logging.basicConfig(filename='{log_path}/{job_id}'.format(log_path=LOG_PATH, job_id=job.id), format='%(levelname)s:%(message)s', level=logging.INFO)
        task_init_log_file(job.id)
        task = Task(kwargs['app_id'], func.__name__, job.id, 'in_progress')
        db.add(task)
        db.commit()
        try:
            task_update_progress(job, 'In Progress', percent=0)
            result = func(db=db, job=job, *args, **kwargs)
            task_update_progress(job, 'Done', percent=100)
            task.status = 'done'
        except CallException, e:
            logging.error(e)
            task_update_progress(job, 'Failed', percent=100)
            task.status = 'failed'
        task_close_log_file()
        db.commit()
    return wrapit


@prepare_task
def task_init_app():
    os.chdir("/ghost")
    try:
        os.makedirs("%s/%s/%s" % (app, env, role))
    except:
        raise CallException("Init app, creating directory")
    os.chdir("/ghost/%s/%s/%s" % (app, env, role))
    gcall("git clone https://%s:%s@%s" % (git_login, git_password, git_path), "Git clone")
    os.chdir(get_git_repo(app))


def task_predeploy_app(app):
    """
    Execute tasks before packaging application (ie: install lib dependencies)
    """
    predeploy = os.path.join(ROOT_PATH, 'predeploy', 'symfony_predeploy.sh')
    shutil.copy(predeploy, get_app_path(app))
    os.chdir(get_app_path(app))
    gcall('./symfony_predeploy.sh %s' % app.env, 'Predeploy script')


def task_postdeploy_app(app):
    """
    Execute tasks after deployment (ie: clear cache)
    """
    postdeploy = os.path.join(ROOT_PATH, 'postdeploy', 'symfony_postdeploy.sh')
    shutil.copy(postdeploy, get_app_path(app))
    os.chdir(get_app_path(app))
    gcall('./symfony_postdeploy.sh %s' % app.env, 'Postdeploy script')

def search_autoscale():
    pass

def start_autoscale():
    pass

def stop_autoscale():
    pass

def sync_instances(app, task_name):
    # os.chdir(ROOT_PATH)
    # cmd = "fab set_hosts:ghost_app={app},ghost_env={env},ghost_role={role} {task_name}".format(app=app.app, env=app.env, role=app.role, task_name=task_name)
    # gcall(cmd, "Updating current instances")
    pass

def connect_db():
    db_path = os.path.join(ROOT_PATH, SQLITE_DB_PATH)
    engine = create_engine('sqlite:///' + db_path, echo=True)
    # create a configured "Session" class
    Session = sessionmaker(bind=engine)
    # create a Session
    session = Session()
    session._model_changes = {}
    return session


def task_update_progress(job, message, **kwargs):
    print(job)
    job.meta['progress_message'] = message
    if kwargs and kwargs['percent']:
        job.meta['progress_completion'] = kwargs['percent']
    job.save()


def task_update_status(db, log, status):
    if log:
        log.status = status
        db.commit()


def get_app_path(app):
    return os.path.join('/', 'ghost', app.app, app.env, app.role, get_git_repo(app))

# FIXME: handle incorrect Git repo path with try/except
def get_git_repo(app):
    git_repo = app.git_path.split('/')
    return git_repo[len(git_repo)-1][:-4]


def task_init_log_file(job_id):
    global log_file
    log_file = open("{log_path}/{job_id}".format(log_path=LOG_PATH, job_id=job_id), 'a')

def task_close_log_file(job_id):
    global log_file
    log_file.close()


@prepare_task
def task_deploy_app(app_id, branch=None, commit=None, job=None, db=None):
    """
    0) Update sourcecode
    1) Stop Autoscaling
    2) Update MANIFEST on S3
    3) Deploy package on Running EC2 instances
    4) Restart Webserver
    5) Start Autoscaling
    """
    app = db.query(CDApp).filter_by(id=app_id).first()
    if not app:
        raise CallException("Application configuration not found")
    os.chdir(get_app_path(app))
    checkout = branch if branch else commit
    if (not checkout):
        raise CallException("No commit/branch specified")
    gcall("git pull", "Git pull")
    gcall("git checkout %s" % checkout, "Git checkout: %s" % checkout)
    task_predeploy_app(app)
    pkg_name = package_app(app)
    manifest, manifest_path = tempfile.mkstemp()
    os.write(manifest, "%s" % pkg_name)
    stop_autoscale()
    gcall("s3cmd put %s %s/%s/%s/%s/MANIFEST" % (manifest_path, app.bucket_s3, app.app, app.env, app.role), "Upload manifest")
    sync_instances(app, 'deploy')
    os.close(manifest)
    start_autoscale()


def package_app(app):
    os.chdir("/ghost/%s/%s/%s/%s" % (app.app, app.env, app.role, get_git_repo(app)))
    pkg_name = "%s_%s.tar.gz" % (datetime.datetime.now().strftime("%Y%m%d%H%M"), get_git_repo(app))
    gcall("tar cvzf ../%s ." % pkg_name, "Creating package: %s" % pkg_name)
    gcall("s3cmd put ../%s %s/%s/%s/%s/" % (pkg_name, app.bucket_s3, app.app, app.env, app.role), "Uploading package: %s" % pkg_name)
    return pkg_name

# task_init_app()
if __name__ == '__main__':
    # task_init_app()
    # task_deploy_app(branch="staging")
    # task_predeploy_app()
    print("Yeah !!!")

