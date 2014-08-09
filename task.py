from subprocess import call
import datetime
import os
import shutil
import tempfile
from boto import ec2

aws_region = 'us-east-1'
branch = "staging"
app = "worldsbestbars"
env = "staging"
role = "webserver"
git_login = "morea-deploy"
git_password = "***REMOVED***"
git_path = "github.com/***REMOVED***.git"
bucket_s3 = "s3://deploy-811874869762"

git_repo = git_path.split('/')
git_repo = git_repo[len(git_repo)-1][:-4]

root_path = os.path.dirname(os.path.realpath(__file__))
app_path = os.path.join('/', 'ghost', app, env, role, git_repo)
log_file = open("/tmp/toto", 'w')

class CallException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


def gcall(args, cmd_description):
    ret = call(args, stdout=log_file, stderr=log_file, shell=True)
    if (ret != 0):
        raise CallException("ERROR: %s" % cmd_description)


def task_init_app():
    os.chdir("/ghost")
    try:
        os.makedirs("%s/%s/%s" % (app, env, role))
    except:
        raise CallException("Init app, creating directory")
    os.chdir("/ghost/%s/%s/%s" % (app, env, role))
    gcall("git clone https://%s:%s@%s" % (git_login, git_password, git_path), "Git clone")
    os.chdir(git_repo)


def task_predeploy_app():
    """
    Execute tasks before packaging application (ie: install lib dependencies)
    """
    predeploy = os.path.join(root_path, 'predeploy', 'symfony_predeploy.sh')
    print("Predeploy path: %s" % predeploy)
    print("App path: %s" % app_path)
    shutil.copy(predeploy, app_path)
    os.chdir(app_path)
    gcall('./symfony_predeploy.sh %s' % env, 'Predeploy script')


def task_postdeploy_app():
    """
    Execute tasks after deployment (ie: clear cache)
    """
    postdeploy = os.path.join(root_path, 'postdeploy', 'symfony_postdeploy.sh')
    shutil.copy(postdeploy, app_path)
    os.chdir(app_path)
    gcall('symfony_postdeploy.sh', 'Postdeploy script')

def search_autoscale():
    pass

def start_autoscale():
    pass

def stop_autoscale():
    pass

def sync_instances():
    pass

def task_deploy_app(branch=None, commit=None):
    """
    0) Update sourcecode
    1) Stop Autoscaling
    2) Update MANIFEST on S3
    3) Deploy package on Running EC2 instances
    4) Restart Webserver
    5) Start Autoscaling
    """
    os.chdir(app_path)
    checkout = branch if branch else commit
    if (not checkout):
        raise CallException("No commit/branch specified")
    gcall("git pull", "Git pull")
    gcall("git checkout %s" % checkout, "Git checkout: %s" % checkout)
    task_predeploy_app()
    pkg_name = package_app()
    manifest, manifest_path = tempfile.mkstemp()
    os.write(manifest, "%s" % pkg_name)
    stop_autoscale()
    gcall("s3cmd put %s %s/%s/%s/%s/MANIFEST" % (manifest_path, bucket_s3, app, env, role), "Upload manifest")
    sync_instances()
    os.close(manifest)
    start_autoscale()

def package_app():
    os.chdir("/ghost/%s/%s/%s/%s" % (app, env, role, git_repo))
    pkg_name = "%s_%s.tar.gz" % (datetime.datetime.now().strftime("%Y%m%d%H%M"), git_repo)
    gcall("tar cvzf ../%s ." % pkg_name, "Creating package: %s" % pkg_name)
    gcall("s3cmd put ../%s %s/%s/%s/%s/" % (pkg_name, bucket_s3, app, env, role), "Uploading package: %s" % pkg_name)
    return pkg_name

# task_init_app()
if __name__ == '__main__':
    # task_init_app()
    task_deploy_app(branch="staging")
    # task_predeploy_app()

