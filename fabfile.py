from fabric.api import run, sudo, task, env, put
from boto import ec2
from task import CallException

def find_ec2_instances(ghost_app, ghost_env, ghost_role, region):
    conn = ec2.connect_to_region(region)
    #reservations = conn.get_all_instances()
    reservations = conn.get_all_instances(filters={"tag:Env": ghost_env, "tag:Role": ghost_role, "tag:App": ghost_app, "instance-state-name":"running"})
    hosts = []
    for reservation in reservations:
        for instance in reservation.instances:
            hosts.append(instance.private_ip_address)
    if (len(hosts) == 0):
        raise CallException("No instance found with tags App:%s, Role:%s, Env:%s" % (ghost_app, ghost_role, ghost_env))
    return hosts

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

