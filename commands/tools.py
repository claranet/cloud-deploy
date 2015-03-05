from subprocess import call
from boto import ec2

class GCallException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def gcall(args, cmd_description, log_fd, dry_run=False):
    log(cmd_description, log_fd)
    log("CMD: {0}".format(args), log_fd)
    if not dry_run:
        ret = call(args, stdout=log_fd, stderr=log_fd, shell=True)
        if (ret != 0):
            raise GCallException("ERROR: %s" % cmd_description)

def find_ec2_instances(ghost_app, ghost_env, ghost_role, region):
    conn = ec2.connect_to_region(region)
    reservations = conn.get_all_instances(filters={"tag:env": ghost_env, \
            "tag:role": ghost_role, "tag:app": ghost_app, \
            "instance-state-name":"running"})
    hosts = []
    for reservation in reservations:
        for instance in reservation.instances:
            hosts.append(instance.private_ip_address)
    if (len(hosts) == 0):
        raise GCallException("No instance found with tags app:%s, role:%s, env:%s, region:%s" \
                        % (ghost_app, ghost_role, ghost_env, region))
    return hosts

def log(message, fd):
    fd.write("{message}\n".format(message=message))

