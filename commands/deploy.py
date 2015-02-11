import os
from pymongo import MongoClient
from tools import GCallException, gcall, log
from initrepo import InitRepo


class Deploy():
    _app = None
    _job = None
    _log_fd = -1
    _app_path = None
    _git_repo = None
    _dry_run = None
    _as_conn = None
    _as_group = None

    def __init__(app, job, log_fd):
        self._app = app
        self._job = job
        self._log_fd = log_fd

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

    def _set_app_path(self):
        self._app_path = os.path.join('/', 'ghost', self._app['app'], self._app['env'], self._app['role'], self._git_repo)


# FIXME: handle incorrect Git repo path with try/except
    def _set_git_repo(self):
        git_repo = self._app['git_repo'].split('/')
        self._git_repo = git_repo[len(git_repo)-1][:-4]


    def _package_app(self):
        os.chdir("/ghost/{app}/{env}/{role}/{0}".format(self._git_repo, **self._app))
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
        pkg_name = "%s_%s.tar.gz" % (timestamp, self._git_repo)
        self._gcall("tar cvzf ../%s . > /dev/null" % pkg_name, "Creating package: %s" % pkg_name)
        self._gcall("aws s3 cp ../{0} {bucket_s3}/{app}/{env}/{role}/".format(pkg_name, **self._app), "Uploading package: %s" % pkg_name)
        return pkg_name

    def _purge_package(self, pkg_name):
        task_name = "purge:{0}".format(pkg_name)
        self._gcall("/usr/local/bin/fab -i {key_path} set_hosts:ghost_app={app},ghost_env={env},ghost_role={role},region={aws_region} {0}".format(task_name, **self._app), "Purging package: %s" % pkg_name)

    def execute():
        """
        0) Update sourcecode
        1) Stop Autoscaling
        2) Update MANIFEST on S3
        3) Deploy package on Running EC2 instances
        4) Restart Webserver
        5) Start Autoscaling
        """
        os.chdir(self._app_path)
        self._gcall("git stash", "Stashing git repository")
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
            pkg_timestamped = self._app['deploy'][0].split('_')[0]
            self._purge_package(pkg_timestamped)
            self._db.apps.update({'_id': self._app['_id']}, { '$pop': {'deploy': -1} })

    def finish():
        pass
