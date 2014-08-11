from fabric.api import run, sudo, task, env, put
from boto import ec2
from task import CallException

def find_ec2_instances(ghost_app, ghost_env, ghost_role):
    conn = ec2.connect_to_region('us-east-1')
    #reservations = conn.get_all_instances()
    reservations = conn.get_all_instances(filters={"tag:Env": ghost_env, "tag:Role": ghost_role, "tag:App": ghost_app})
    res = []
    for reservation in reservations:
        instance = reservation.instances[0]
        res.append(instance.private_ip_address)
    if (len(res) == 0):
        raise CallException("No instance found with tags App:%s, Role:%s, Env:%s" % (app, role, env))
    return res

@task
def deploy():
    sudo('rm -f /tmp/boostrap.sh')
    put('postdeploy/bootstrap.sh', '/tmp/')
    sudo('chmod +x /tmp/bootstrap.sh')
    sudo('/tmp/bootstrap.sh')


@task
def set_hosts(ghost_app=None, ghost_env=None, ghost_role=None):
    env.hosts = find_ec2_instances(ghost_app, ghost_env, ghost_role)
    print(env.hosts)

