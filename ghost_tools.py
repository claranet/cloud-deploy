import os
from subprocess import call
import yaml

from jinja2 import Environment, FileSystemLoader

import boto.ec2.autoscale
import boto.ec2.blockdevicemapping
import boto.s3

from ghost_log import log

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))

with open(os.path.dirname(os.path.realpath(__file__)) + '/config.yml', 'r') as conf_file:
    config = yaml.load(conf_file)

def render_stage2(config, s3_region):
    """
    Renders the stage2 script that is the second step of EC2 instance bootstrapping through userdata (stage1).

    The 'config' dict should contain the following parameters:
    * 'bucket_s3': name of the Ghost S3 bucket (required)
    * 'ghost_root_path': path to the root of the Ghost installation (required)
    * 'max_deploy_history': maximum number of deployments to preserve after a deployment (optional).

    If 'max_deploy_history' is not defined in the 'config' dict, the render_stage2() function uses 3 as the default value:

    >>> config = {'bucket_s3': 'my-s3-bucket', 'ghost_root_path': '.'}
    >>> stage2 = render_stage2(config, 'eu-west-1')
    >>> stage2[stage2.find('S3_BUCKET'):stage2.find('\\n', stage2.find('S3_BUCKET')+1)]
    u'S3_BUCKET=my-s3-bucket'
    >>> stage2[stage2.find('S3_REGION'):stage2.find('\\n', stage2.find('S3_REGION')+1)]
    u'S3_REGION=eu-west-1'
    >>> stage2[stage2.find('MAX_DEPLOY_HISTORY'):stage2.find('\\n', stage2.find('MAX_DEPLOY_HISTORY')+1)]
    u'MAX_DEPLOY_HISTORY="3"'

    This can be overridden by defining the 'max_deploy_history' configuration setting:

    >>> config = {'bucket_s3': 'my-s3-bucket', 'ghost_root_path': '.', 'max_deploy_history': 1}
    >>> stage2 = render_stage2(config, 'ap-northeast-1')
    >>> stage2[stage2.find('S3_BUCKET'):stage2.find('\\n', stage2.find('S3_BUCKET')+1)]
    u'S3_BUCKET=my-s3-bucket'
    >>> stage2[stage2.find('S3_REGION'):stage2.find('\\n', stage2.find('S3_REGION')+1)]
    u'S3_REGION=ap-northeast-1'
    >>> stage2[stage2.find('MAX_DEPLOY_HISTORY'):stage2.find('\\n', stage2.find('MAX_DEPLOY_HISTORY')+1)]
    u'MAX_DEPLOY_HISTORY="1"'
    """
    bucket_s3 = config['bucket_s3']
    ghost_root_path = config['ghost_root_path']
    max_deploy_history = config.get('max_deploy_history', 3)

    jinja_templates_path='%s/scripts' % ghost_root_path
    if(os.path.exists('%s/stage2' % jinja_templates_path)):
        loader=FileSystemLoader(jinja_templates_path)
        jinja_env = Environment(loader=loader)
        template = jinja_env.get_template('stage2')
        return template.render(bucket_s3=bucket_s3, max_deploy_history=max_deploy_history, bucket_region=s3_region)
    return None

def refresh_stage2(region, config):
    """
    Will update the second phase of bootstrap script on S3
    """
    conn = boto.s3.connect_to_region(region)
    bucket_s3 = config['bucket_s3']
    bucket = conn.get_bucket(bucket_s3)
    stage2 = render_stage2(config, region)
    if stage2 is not None:
        key = bucket.new_key("/ghost/stage2")
        key.set_contents_from_string(stage2)
        key.close()
    else:
        bucket.delete_key("/ghost/stage2")


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

def get_rq_name_from_app(app):
    """
    Returns an RQ name for a given ghost app.

    The default strategy is to use one worker per app:

    >>> config['rq_worker_strategy'] = None
    >>> get_rq_name_from_app({'env': 'prod', 'name': 'App1', 'role': 'webfront'})
    'prod:App1:webfront'

    >>> config['rq_worker_strategy'] = 'one_worker_per_app'
    >>> get_rq_name_from_app({'env': 'prod', 'name': 'App1', 'role': 'webfront'})
    'prod:App1:webfront'

    An alternative strategy is to use one worker per env:

    >>> config['rq_worker_strategy'] = 'one_worker_per_env'
    >>> get_rq_name_from_app({'env': 'prod', 'name': 'App1', 'role': 'webfront'})
    'prod:*:*'

    Another alternative strategy is to use a single worker for all:

    >>> config['rq_worker_strategy'] = 'one_worker_for_all'
    >>> get_rq_name_from_app({'env': 'prod', 'name': 'App1', 'role': 'webfront'})
    'default:*:*'
    """
    rq_worker_strategy = config.get('rq_worker_strategy', 'one_worker_per_app')
    env=app['env']
    name=app['name']
    role=app['role']

    if rq_worker_strategy == 'one_worker_per_env':
        name = role = '*'

    if rq_worker_strategy == 'one_worker_for_all':
        name = role = '*'
        env = 'default'

    return '{env}:{name}:{role}'.format(env=env, name=name, role=role)

def get_app_from_rq_name(name):
    """
    Returns an app's env, name, role for a given RQ name

    >>> sorted(get_app_from_rq_name('prod:App1:webfront').items())
    [('env', 'prod'), ('name', 'App1'), ('role', 'webfront')]
    """
    parts = name.split(':')
    return {'env': parts[0], 'name': parts[1], 'role': parts[2]}

def clean_local_module_workspace(app_path, all_app_modules_list, log_file):
    """
    Walk through app_path directory and check if module workspace should be cleaned.
    """

    log('Cleaning old module workspaces', log_file)
    for mod_dir in os.listdir(app_path):
        if not mod_dir in all_app_modules_list:
            gcall('rm -rf "{p}"'.format(p=os.path.join(app_path, mod_dir)), 'Removing deleted module : %s' % mod_dir, log_file)

def get_app_module_name_list(modules):
    """
    Returns the list of module name from a Ghost App
    """
    return [app_module['name'] for app_module in modules if 'name' in app_module]
