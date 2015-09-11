from datetime import datetime
from subprocess import call
from boto import ec2
import boto.ec2.autoscale
from boto.ec2.autoscale import LaunchConfiguration
from boto import s3
import time
from jinja2 import Environment, FileSystemLoader
import os

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))

class GCallException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def gcall(args, cmd_description, log_fd, dry_run=False, env=None):
    log(cmd_description, log_fd)
    log("CMD: {0}".format(args), log_fd)
    if not dry_run:
        ret = call(args, stdout=log_fd, stderr=log_fd, shell=True, env=env)
        if (ret != 0):
            raise GCallException("ERROR: %s" % cmd_description)

def find_ec2_instances(ghost_app, ghost_env, ghost_role, region):
    conn_as = boto.ec2.autoscale.connect_to_region(region)
    conn = ec2.connect_to_region(region)
    instances = conn.get_only_instances(filters={"tag:env": ghost_env,
                                                 "tag:role": ghost_role,
                                                 "tag:app": ghost_app,
                                                 "instance-state-name": "running"})
    hosts = []
    for instance in instances:
        # Instances in autoscale "Terminating:*" states are still "running" but no longer in the Load Balancer
        autoscale_instances = conn_as.get_all_autoscaling_instances(instance_ids=[instance.id])
        if not autoscale_instances or not autoscale_instances[0].lifecycle_state in ['Terminating:Wait', 'Terminating:Proceed']:
            hosts.append(instance.private_ip_address)
    if (len(hosts) == 0):
        raise GCallException("No instance found with tags app:%s, role:%s, env:%s, region:%s" \
                        % (ghost_app, ghost_role, ghost_env, region))
    return hosts

def execute_task_on_hosts(task_name, app_name, app_env, app_role, app_region, key_path, log_file):
    hosts = find_ec2_instances(app_name, app_env, app_role, app_region)
    if len(hosts) > 0:
        hosts_list = ','.join(hosts)
        cmd = "/usr/local/bin/fab --show=debug --fabfile={root_path}/fabfile.py -i {key_path} --hosts={hosts_list} {task_name}".format(root_path=ROOT_PATH,
                                                                                                                                       key_path=key_path,
                                                                                                                                       hosts_list=hosts_list,
                                                                                                                                       task_name=task_name)
        gcall(cmd, "Updating current instances", log_file)
    else:
        log("WARNING: no instance available to sync deployment", log_file)

def log(message, fd):
    fd.write("{timestamp}: {message}\n".format(timestamp=datetime.now().strftime("%Y/%m/%d %H:%M:%S GMT"), message=message))

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
    if(os.path.exists('%s/stage1' % jinja_templates_path)):
        loader=FileSystemLoader(jinja_templates_path)
        jinja_env = Environment(loader=loader)
        template = jinja_env.get_template('stage1')
        userdata = template.render(bucket_s3=bucket_s3)
        return userdata
    else:
        return ""

def refresh_stage2(bucket_s3, region, root_ghost_path):
    """
    Will update the second phase of boostrap script on S3
    """
    conn = s3.connect_to_region(region)
    bucket = conn.get_bucket(bucket_s3)
    k = bucket.new_key("/ghost/stage2")
    jinja_templates_path='%s/scripts' % root_ghost_path
    print("Before check path")
    if(os.path.exists('%s/stage2' % jinja_templates_path)):
        loader=FileSystemLoader(jinja_templates_path)
        jinja_env = Environment(loader=loader)
        template = jinja_env.get_template('stage2')
        stage2 = template.render(bucket_s3=bucket_s3)
        k.set_contents_from_string(stage2)


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

    if launchconfigs and len(launchconfigs) > retention:
        launchconfigs.sort(key=lambda lc: lc.created_time, reverse=True)
        i = 0
        while i < retention:
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
    if 'type' in rbd:
        dev_sda1.volume_type = rbd['type']
    else:
        dev_sda1.volume_type = "gp2"
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
