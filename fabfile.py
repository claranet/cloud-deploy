import os
from fabric.api import run, sudo, task, env, put
from commands.tools import GCallException, find_ec2_instances
from jinja2 import Environment, FileSystemLoader

@task
def purge(pkg_name):
    sudo('rm -rf /ghost/{0}'.format(pkg_name))

@task
def deploy(bucket_s3, module):
    bootstrap, bootstrap_path = tempfile.mkstemp()
    jinja_env = Environment(loader=FileSystemLoader('scripts'))
    template = jinja_env.get_template('bootstrap.sh')
    template.render(bucket_s3=bucket_s3).stream(name='bootstrap').dump(bootstrap_path)
    sudo('rm -f /tmp/boostrap.sh')
    put('%s' % bootstrap_path, '/tmp/bootstrap.sh')
    os.remove(bootstrap_path)
    sudo('chmod +x /tmp/bootstrap.sh')
    sudo('/tmp/bootstrap.sh %s' % module)

@task
def set_hosts(ghost_app=None, ghost_env=None, ghost_role=None, region=None):
    env.hosts = find_ec2_instances(ghost_app, ghost_env, ghost_role, region)
    print(env.hosts)

