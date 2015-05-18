from subprocess import call
from boto import ec2
import boto.ec2.autoscale
from boto.ec2.autoscale import LaunchConfiguration
from boto.ec2.autoscale import AutoScaleConnection
from boto.ec2.blockdevicemapping import EBSBlockDeviceType, BlockDeviceMapping
import time
from jinja2 import Environment, FileSystemLoader
import os

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

def create_launch_config(app, userdata, ami_id):
    d = time.strftime('%d%m%Y-%H%M',time.localtime())
    launch_config_name = "launchconfig.{0}.{1}.{2}.{3}.{4}".format(app['env'], app['region'], app['role'], app['name'], d)
    conn_as = boto.ec2.autoscale.connect_to_region(app['region'])
    if 'root_block_device' in app['environment_infos']:
        bdm = create_block_device(app['environment_infos']['root_block_device'])
    else:
        bdm = create_block_device()
    launch_config = LaunchConfiguration(name=launch_config_name, \
        image_id=ami_id, key_name=app['environment_infos']['key_name'], \
        security_groups=app['environment_infos']['security_groups'], \
        user_data=userdata, instance_type=app['instance_type'], kernel_id=None, \
        ramdisk_id=None, block_device_mappings=[bdm], \
        instance_monitoring=False, spot_price=None, \
        instance_profile_name=app['environment_infos']['instance_profile'], ebs_optimized=False, \
        associate_public_ip_address=True, volume_type=None, \
        delete_on_termination=True, iops=None, \
        classic_link_vpc_id=None, classic_link_vpc_security_groups=None)
    conn_as.create_launch_configuration(launch_config)
    return launch_config

def generate_userdata(bucket_s3, root_ghost_path):
    jinja_templates_path='%s/scripts' % root_ghost_path
    if(os.path.exists('%s/bootstrap.sh' % jinja_templates_path)):
        loader=FileSystemLoader(jinja_templates_path)
        jinja_env = Environment(loader=loader)
        template = jinja_env.get_template('bootstrap.sh')
        userdata = template.render(bucket_s3=bucket_s3)
        return userdata

def check_autoscale_exists(as_name, region):
    conn_as = boto.ec2.autoscale.connect_to_region(region)
    autoscale = conn_as.get_all_groups(names=[as_name])
    if autoscale:
        return True
    else:
        return False

def purge_launch_configuration(app):
    conn_as = boto.ec2.autoscale.connect_to_region(app['region'])
    retention = 2
    lcs = []
    launchconfigs = []
    lcs = conn_as.get_all_launch_configurations()

    launchconfig_format = "launchconfig.{0}.{1}.{2}.{3}.".format(app['env'], app['region'], app['role'], app['name'])

    for lc in lcs:
        if launchconfig_format in lc.name:
            launchconfigs.append(lc)
    if launchconfigs:
        launchconfigs.sort(key=lambda lc: lc.created_time, reverse=True)
        i = 0
        while i < retention:
            if launchconfigs[0]:
                launchconfigs.pop(0)
            i += 1

        for lc in launchconfigs:
            conn_as.delete_launch_configuration(lc.name)

    #Check if the purge works : current_version and current_version -1 are not removed.
    lcs = []
    launchconfigs = []
    lcs = conn_as.get_all_launch_configurations()
    for lc in lcs:
        if launchconfig_format in lc.name:
            launchconfigs.append(lc)
    if len(launchconfigs) <= 2:
        return True
    else:
        return False

def create_block_device(rbd={}):
    dev_sda1 = boto.ec2.blockdevicemapping.EBSBlockDeviceType(delete_on_termination=True)
    if 'size' in rbd:
        dev_sda1.size = rbd['size']
    else:
        rbd['size'] = 10
        dev_sda1.size = rbd['size']
    bdm = boto.ec2.blockdevicemapping.BlockDeviceMapping()
    if 'name' in rbd:
        bdm[rbd['name']] = dev_sda1
    else:
        rbd['name'] = "/dev/xvda"
        bdm[rbd['name']] = dev_sda1
    return bdm
