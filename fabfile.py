import os, tempfile
from fabric.api import run, sudo, task, env, put, settings
from commands.tools import GCallException, find_ec2_instances
from jinja2 import Environment, FileSystemLoader
env.user = 'admin'

@task
def purge(pkg_name):
    sudo('rm -rf /ghost/{0}'.format(pkg_name))

@task
def deploy(bucket_s3, module):
    with settings(warn_only=True):
        bootstrap, bootstrap_path = tempfile.mkstemp()
        jinja_env = Environment(loader=FileSystemLoader('%s/scripts' % os.path.dirname(os.path.realpath(__file__))))
        template = jinja_env.get_template('bootstrap.sh')
        #template.render(bucket_s3=bucket_s3).stream(name='bootstrap').dump(bootstrap_path)
        template.stream(bucket_s3=bucket_s3).dump(bootstrap_path)
        sudo('rm -rvf /tmp/bootstrap.sh')
        put('%s' % bootstrap_path, '/tmp/bootstrap.sh')
        os.remove(bootstrap_path)
        sudo('chmod +x /tmp/bootstrap.sh')
        sudo('/tmp/bootstrap.sh %s' % module)

@task
def set_hosts(ghost_app=None, ghost_env=None, ghost_role=None, region=None):
    env.hosts = find_ec2_instances(ghost_app, ghost_env, ghost_role, region)
    print(env.hosts)
