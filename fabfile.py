from fabric.api import run, sudo, task, env, put
from boto import ec2
from commands.tools import GCallException, find_ec2_instances

@task
def purge(pkg_name):
    sudo('rm -rf /ghost/{0}'.format(pkg_name))

@task
def deploy():
    sudo('rm -f /tmp/boostrap.sh')
    put('postdeploy/bootstrap.sh', '/tmp/')
    sudo('chmod +x /tmp/bootstrap.sh')
    sudo('/tmp/bootstrap.sh')


@task
def set_hosts(ghost_app=None, ghost_env=None, ghost_role=None, region=None):
    env.hosts = find_ec2_instances(ghost_app, ghost_env, ghost_role, region)
    print(env.hosts)

