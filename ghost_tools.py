# -*- coding: utf-8 -*-
from base64 import b64decode, b64encode

import os
from subprocess import call
import yaml
import copy
from sh import git
from datetime import datetime, timedelta

from jinja2 import Environment, FileSystemLoader

from ghost_log import log

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))

with open(os.path.dirname(os.path.realpath(__file__)) + '/config.yml', 'r') as conf_file:
    config = yaml.load(conf_file)

try:
    CURRENT_REVISION_NAME = git('symbolic-ref', '-q', '--short', 'HEAD', _tty_out=False).strip()
except:
    try:
        CURRENT_REVISION_NAME = git('describe', '--tags', '--exact-match', _tty_out=False).strip()
    except:
        CURRENT_REVISION_NAME = git('--no-pager', 'rev-parse', '--short', 'HEAD', _tty_out=False).strip()

try:
    CURRENT_REVISION = dict(
        current_revision=git('--no-pager', 'rev-parse', '--short', 'HEAD', _tty_out=False).strip(),
        current_revision_date=git('log', '-1', '--format=%cD', _tty_out=False).strip(),
        current_revision_name=CURRENT_REVISION_NAME.strip()
    )
except:
    CURRENT_REVISION = dict(
        current_revision='unknown',
        current_revision_date='unknown',
        current_revision_name='unknown'
    )

GHOST_JOB_STATUSES_COLORS = {
    'failed':    '#F44336',
    'cancelled': '#333333',
    'aborted':   '#AAAAAA',
    'started':   '#03A9F4',
    'done':      '#4CAF50',
    'default':   '#415560',
}


def get_aws_connection_data(assumed_account_id, assumed_role_name, assumed_region_name=""):
    """
    Build a key-value dictionnatiory args for aws cross  connections
    """
    if assumed_account_id and assumed_role_name:
        aws_connection_data = dict(
            [("assumed_account_id", assumed_account_id), ("assumed_role_name", assumed_role_name),
             ("assumed_region_name", assumed_region_name)])
    else:
        aws_connection_data = dict()
    return (aws_connection_data)


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

    jinja_templates_path = '%s/scripts' % ghost_root_path
    if (os.path.exists('%s/stage2' % jinja_templates_path)):
        loader = FileSystemLoader(jinja_templates_path)
        jinja_env = Environment(loader=loader)
        template = jinja_env.get_template('stage2')
        return template.render(bucket_s3=bucket_s3, max_deploy_history=max_deploy_history, bucket_region=s3_region)
    return None


def refresh_stage2(cloud_connection, region, config):
    """
    Will update the second phase of bootstrap script on S3
    """
    conn = cloud_connection.get_connection(region, ["s3"])
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


def get_app_colored_env(app):
    color = app['blue_green'].get('color', None) if app.get('blue_green') else None
    if color:
        return '{env}-{color}'.format(color=color, env=app['env'])
    else:
        return app['env']


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
    env = get_app_colored_env(app)
    name = app['name']
    role = app['role']

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
            gcall('rm -rf "{p}"'.format(p=os.path.join(app_path, mod_dir)), 'Removing deleted module : %s' % mod_dir,
                  log_file)


def get_app_module_name_list(modules):
    """
    Returns the list of module name from a Ghost App

    >>> modules = [{
    ...    "name" : "symfony2",
    ...    "post_deploy" : "Y29tcG9zZXIgaW5zdGFsbCAtLW5vLWludGVyYWN0aW9u",
    ...    "pre_deploy" : "ZXhpdCAx",
    ...    "scope" : "code",
    ...    "initialized" : False,
    ...    "path" : "/var/www",
    ...    "git_repo" : "https://github.com/symfony/symfony-demo"
    ... }]
    >>> get_app_module_name_list(modules)
    ['symfony2']

    >>> modules = [{
    ...    "initialized" : False,
    ...    "path" : "/var/www",
    ...    "git_repo" : "https://github.com/symfony/symfony-demo"
    ... }]
    >>> get_app_module_name_list(modules)
    []

    >>> modules = [{
    ...    "name" : "mod1",
    ...    "initialized" : False,
    ...    "path" : "/var/www",
    ...    "git_repo" : "https://github.com/symfony/symfony-demo"
    ...  },{
    ...    "name" : "mod-name2",
    ...    "initialized" : False,
    ...    "path" : "/var/www",
    ...    "git_repo" : "https://github.com/symfony/symfony-demo"
    ... }]
    >>> get_app_module_name_list(modules)
    ['mod1', 'mod-name2']

    >>> modules = [{
    ...    "name" : "mod1",
    ...    "initialized" : False,
    ...    "path" : "/var/www",
    ...    "git_repo" : "https://github.com/symfony/symfony-demo"
    ...  },{
    ...    "noname" : "mod-name2",
    ...    "initialized" : False,
    ...    "path" : "/var/www",
    ...    "git_repo" : "https://github.com/symfony/symfony-demo"
    ...  },{
    ...    "name" : "mod3",
    ...    "initialized" : False,
    ...    "path" : "/var/www",
    ...    "git_repo" : "https://github.com/symfony/symfony-demo"
    ... }]
    >>> get_app_module_name_list(modules)
    ['mod1', 'mod3']

    """
    return [app_module['name'] for app_module in modules if 'name' in app_module]


def b64decode_utf8(ascii):
    u"""
    Converts an ASCII UTF8/base64 encoded string to a unicode string

    >>> b64decode_utf8(None)

    >>> b64decode_utf8('')
    u''

    >>> b64decode_utf8('aGVsbG8=')
    u'hello'

    >>> b64decode_utf8('w6ljaG8=')
    u'\\xe9cho'
    """
    if ascii is not None:
        return b64decode(ascii).decode('utf-8')


def b64encode_utf8(string):
    u"""
    Converts an ASCII or unicode string to an ASCII UTF8/base64 encoded string

    >>> b64encode_utf8(None)

    >>> b64encode_utf8('')
    ''

    >>> b64encode_utf8(u'')
    ''

    >>> b64encode_utf8('hello')
    'aGVsbG8='

    >>> b64encode_utf8(u'écho')
    'w6ljaG8='

    >>> b64encode_utf8(u'\\xe9cho')
    'w6ljaG8='
    """
    if string is not None:
        return b64encode(string.encode('utf-8'))


def ghost_app_object_copy(app, user):
    """
    Returns a clean copy of a Ghost application
    by removing Eve fields and ReadOnly fields
    """
    copy_app = copy.deepcopy(app)
    if user:
        copy_app['user'] = user
    if 'modules' in copy_app:
        for copy_module in copy_app['modules']:
            # Remove 'initialized' RO fields
            if 'initialized' in copy_module:
                del copy_module['initialized']
            if 'last_deployment' in copy_module:
                del copy_module['last_deployment']
    if 'autoscale' in copy_app and 'current' in copy_app['autoscale']:
        del copy_app['autoscale']['current']
    # Remove RO fields
    if 'blue_green' in copy_app and 'alter_ego_id' in copy_app['blue_green']:
        del copy_app['blue_green']['alter_ego_id']
    if 'ami' in copy_app:
        del copy_app['ami']
    if 'build_infos' in copy_app and 'ami_name' in copy_app['build_infos']:
        del copy_app['build_infos']['ami_name']
    # Cleaning Eve Fields
    del copy_app['_id']
    del copy_app['_etag']
    del copy_app['_version']
    del copy_app['_created']
    del copy_app['_updated']
    # Cleaning Eve response meta from internal_post
    if '_latest_version' in copy_app:
        del copy_app['_latest_version']
    if '_status' in copy_app:
        del copy_app['_status']
    if '_links' in copy_app:
        del copy_app['_links']

    return copy_app


def get_app_friendly_name(app):
    """
    >>> my_app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'autoscale': {'name': 'asg-mod1'}, 'environment_infos': {'instance_tags':[]}}
    >>> get_app_friendly_name(my_app)
    'app1/prod/webfront'

    """
    return "{0}/{1}/{2}".format(app['name'], app['env'], app['role'])


def boolify(val):
    """
    Returns a boolean even if 'val' is a string or already a boolean

    >>> boolify(None)
    False

    >>> boolify(False)
    False

    >>> boolify('')
    False

    >>> boolify(u'')
    False

    >>> boolify('False')
    False

    >>> boolify('True')
    True

    >>> boolify('true')
    True

    >>> boolify('1')
    True

    >>> boolify(True)
    True
    """
    if isinstance(val, bool):
        return val
    return val in ['TRUE', 'True', 'true', '1', 1, 'Yes', 'Y', 'YES', 'y']


def get_running_jobs(_db, app_id_1, app_id_2, current_job):
    """
    Get all running jobs for given app Ids
    """
    finished_states = ["done", "failed", "aborted", "cancelled"]
    date_limit = datetime.utcnow() - timedelta(hours=3)
    jobs = _db.jobs.find({
        "$or": [{"app_id": app_id_1}, {"app_id": app_id_2}],
        "_id": {"$ne": current_job},
        "status": {"$nin": finished_states},
        "_created": {"$gt": date_limit}
    })
    return list(jobs)


def get_module_package_rev_from_manifest(bucket, manifest_key_path, module):
    """
    Parse the Ghost manifest, look for the module, return the associated package name
    """
    manifest_key = bucket.get_key(manifest_key_path)
    manifest = manifest_key.get_contents_as_string()
    for pkgs in manifest.splitlines():
        manifest_module_infos = pkgs.split(":")
        manifest_module_name = manifest_module_infos[0]
        manifest_module_pkg_name = manifest_module_infos[1]
        if manifest_module_name == module:
            return manifest_module_pkg_name
            break
    return None


def keep_n_recent_elements_from_list(keys_list, nb_elt_to_keep, log_file=None):
    """
    Takes a list of elements in argument, sort it (by name) and returns a slice of this list with oldest elements.

    >>> keys_list = [u'1485857801_dummy_0d23e96', u'1485857958_dummy_0d23e96', u'1485858044_dummy_0d23e96', u'1485858360_dummy_0d23e96', u'1485858501_dummy_0d23e96', u'1485878943_dummy_0d23e96', u'1485879061_dummy_0d23e96', u'1485879482_dummy_0d23e96', u'1485880106_dummy_0d23e96', u'1485880663_dummy_0d23e96', u'1485880937_dummy_0d23e96', u'1485881507_dummy_0d23e96', u'1485881708_dummy_0d23e96', u'1485881904_dummy_0d23e96', u'1485882291_dummy_0d23e96', u'1485882416_dummy_0d23e96', u'1485882573_dummy_0d23e96', u'1485882712_dummy_0d23e96', u'1485883002_dummy_0d23e96', u'1485883123_dummy_0d23e96', u'1485964701_dummy_0d23e96', u'1486052064_dummy_0d23e96', u'1486052325_dummy_0d23e96', u'1486052517_dummy_0d23e96', u'1486053100_dummy_0d23e96', u'1486053277_dummy_0d23e96', u'1486120220_dummy_0d23e96', u'1486120350_dummy_0d23e96', u'1486481186_dummy_0d23e96']
    >>> keep_n_recent_elements_from_list(keys_list, 1)
    [u'1485857801_dummy_0d23e96', u'1485857958_dummy_0d23e96', u'1485858044_dummy_0d23e96', u'1485858360_dummy_0d23e96', u'1485858501_dummy_0d23e96', u'1485878943_dummy_0d23e96', u'1485879061_dummy_0d23e96', u'1485879482_dummy_0d23e96', u'1485880106_dummy_0d23e96', u'1485880663_dummy_0d23e96', u'1485880937_dummy_0d23e96', u'1485881507_dummy_0d23e96', u'1485881708_dummy_0d23e96', u'1485881904_dummy_0d23e96', u'1485882291_dummy_0d23e96', u'1485882416_dummy_0d23e96', u'1485882573_dummy_0d23e96', u'1485882712_dummy_0d23e96', u'1485883002_dummy_0d23e96', u'1485883123_dummy_0d23e96', u'1485964701_dummy_0d23e96', u'1486052064_dummy_0d23e96', u'1486052325_dummy_0d23e96', u'1486052517_dummy_0d23e96', u'1486053100_dummy_0d23e96', u'1486053277_dummy_0d23e96', u'1486120220_dummy_0d23e96', u'1486120350_dummy_0d23e96']

    >>> keys_list = [u'1485857801_dummy_0d23e96', u'1485857958_dummy_0d23e96', u'1485858044_dummy_0d23e96', u'1485858360_dummy_0d23e96', u'1485858501_dummy_0d23e96', u'1485878943_dummy_0d23e96', u'1485879061_dummy_0d23e96', u'1485879482_dummy_0d23e96', u'1485880106_dummy_0d23e96', u'1485880663_dummy_0d23e96', u'1485880937_dummy_0d23e96', u'1485881507_dummy_0d23e96', u'1485881708_dummy_0d23e96', u'1485881904_dummy_0d23e96', u'1485882291_dummy_0d23e96', u'1485882416_dummy_0d23e96', u'1485882573_dummy_0d23e96', u'1485882712_dummy_0d23e96', u'1485883002_dummy_0d23e96', u'1485883123_dummy_0d23e96', u'1485964701_dummy_0d23e96', u'1486052064_dummy_0d23e96', u'1486052325_dummy_0d23e96', u'1486052517_dummy_0d23e96', u'1486053100_dummy_0d23e96', u'1486053277_dummy_0d23e96', u'1486120220_dummy_0d23e96', u'1486120350_dummy_0d23e96', u'1486481186_dummy_0d23e96']
    >>> keep_n_recent_elements_from_list(keys_list, 60)
    []

    >>> keys_list = [u'1485857801_dummy_0d23e96', u'1485857958_dummy_0d23e96', u'1485858044_dummy_0d23e96', u'1485858360_dummy_0d23e96', u'1485858501_dummy_0d23e96', u'1485878943_dummy_0d23e96', u'1485879061_dummy_0d23e96', u'1485879482_dummy_0d23e96', u'1485880106_dummy_0d23e96', u'1485880663_dummy_0d23e96', u'1485880937_dummy_0d23e96', u'1485881507_dummy_0d23e96', u'1485881708_dummy_0d23e96', u'1485881904_dummy_0d23e96', u'1485882291_dummy_0d23e96', u'1485882416_dummy_0d23e96', u'1485882573_dummy_0d23e96', u'1485882712_dummy_0d23e96', u'1485883002_dummy_0d23e96', u'1485883123_dummy_0d23e96', u'1485964701_dummy_0d23e96', u'1486052064_dummy_0d23e96', u'1486052325_dummy_0d23e96', u'1486052517_dummy_0d23e96', u'1486053100_dummy_0d23e96', u'1486053277_dummy_0d23e96', u'1486120220_dummy_0d23e96', u'1486120350_dummy_0d23e96', u'1486481186_dummy_0d23e96']
    >>> keep_n_recent_elements_from_list(keys_list, 10)
    [u'1485857801_dummy_0d23e96', u'1485857958_dummy_0d23e96', u'1485858044_dummy_0d23e96', u'1485858360_dummy_0d23e96', u'1485858501_dummy_0d23e96', u'1485878943_dummy_0d23e96', u'1485879061_dummy_0d23e96', u'1485879482_dummy_0d23e96', u'1485880106_dummy_0d23e96', u'1485880663_dummy_0d23e96', u'1485880937_dummy_0d23e96', u'1485881507_dummy_0d23e96', u'1485881708_dummy_0d23e96', u'1485881904_dummy_0d23e96', u'1485882291_dummy_0d23e96', u'1485882416_dummy_0d23e96', u'1485882573_dummy_0d23e96', u'1485882712_dummy_0d23e96', u'1485883002_dummy_0d23e96']

    >>> keep_n_recent_elements_from_list([1,2,3,4,5,6,7,8,9,10], 8)
    [1, 2]

    >>> keep_n_recent_elements_from_list([10,9,8,2,3,4,5,6,7,1], 8)
    [1, 2]

    """
    if log_file:
        log("List contains %s element(s)" % str(len(keys_list)), log_file)
        log("%s most recent element(s) must be kept" % str(nb_elt_to_keep), log_file)

    keys_list.sort()
    del keys_list[(len(keys_list) - nb_elt_to_keep):]

    if log_file:
        log("List now contains %s element(s)" % str(len(keys_list)), log_file)
    return keys_list


def split_hosts_list(hosts_list, split_type, log_file=None):
    """
    Return a list of multiple hosts list for the safe deployment.

        :param hosts_list      list: Dictionnaries instances infos(id and private IP).
        :param split_type:     string:  The way to split the hosts list(1by1-1/3-25%-50%).
        :return                list:    Multiple hosts list or raise an Exception is the safe
                                        deployment process cannot be perform.

    >>> from io import StringIO

    >>> hosts_list = ['host1', 'host2']
    >>> split_hosts_list(hosts_list, '50%')
    [['host1'], ['host2']]
    >>> split_hosts_list(hosts_list, '1by1')
    [['host1'], ['host2']]

    >>> hosts_list = ['host1', 'host2', 'host3']
    >>> split_hosts_list(hosts_list, '50%')
    [['host1', 'host3'], ['host2']]
    >>> split_hosts_list(hosts_list, '1/3')
    [['host1'], ['host2'], ['host3']]
    >>> split_hosts_list(hosts_list, '1by1')
    [['host1'], ['host2'], ['host3']]

    >>> hosts_list = ['host1', 'host2', 'host3', 'host4']
    >>> split_hosts_list(hosts_list, '50%')
    [['host1', 'host3'], ['host2', 'host4']]
    >>> split_hosts_list(hosts_list, '1/3')
    [['host1', 'host4'], ['host2'], ['host3']]
    >>> split_hosts_list(hosts_list, '25%')
    [['host1'], ['host2'], ['host3'], ['host4']]
    >>> split_hosts_list(hosts_list, '1by1')
    [['host1'], ['host2'], ['host3'], ['host4']]

    >>> hosts_list = ['host1', 'host2', 'host3', 'host4', 'host5']
    >>> split_hosts_list(hosts_list, '50%')
    [['host1', 'host3', 'host5'], ['host2', 'host4']]
    >>> split_hosts_list(hosts_list, '1/3')
    [['host1', 'host4'], ['host2', 'host5'], ['host3']]
    >>> split_hosts_list(hosts_list, '25%')
    [['host1', 'host5'], ['host2'], ['host3'], ['host4']]
    >>> split_hosts_list(hosts_list, '1by1')
    [['host1'], ['host2'], ['host3'], ['host4'], ['host5']]
    """

    if split_type == '1by1' and len(hosts_list) > 1:
        return [hosts_list[i:i + 1] for i in range(0, len(hosts_list), 1)]
    elif split_type == '1/3' and len(hosts_list) > 2:
        chunk = 3
    elif split_type == '25%' and len(hosts_list) > 3:
        chunk = 4
    elif split_type == '50%' and len(hosts_list) >= 2:
        chunk = 2
    else:
        if log_file:
            log("Not enough instances to perform safe deployment. Number of instances: \
                {0} for safe deployment type: {1}".format(str(len(hosts_list)), str(split_type)), log_file)
        raise GCallException("Cannot continue, not enought instances to perform the safe deployment")
    return [hosts_list[i::chunk] for i in range(chunk)]


def get_job_log_remote_path(worker_job_id):
    return "{log_dir}/{job_id}.txt".format(log_dir="log/job/", job_id=worker_job_id)


def get_provisioners_config(last_config=None):
    """
    >>> get_provisioners_config(last_config={'dummy': 'dummy'}).keys()
    ['salt']

    >>> get_provisioners_config(last_config={'dummy': 'dummy'})['salt']['git_repo']
    'git@bitbucket.org:morea/morea-salt-formulas.git'

    """
    if not last_config:
        last_config = config
    provisioners_config = last_config.get('features_provisioners', {
        'salt': {
            'git_repo': last_config.get('salt_formulas_repo', 'git@bitbucket.org:morea/morea-salt-formulas.git'),
            'git_revision': last_config.get('salt_formulas_branch', 'master'),
        }
    })
    return provisioners_config


def get_available_provisioners_from_config(last_config=None):
    provisioners_config = get_provisioners_config(last_config)
    return provisioners_config.keys()


def get_ghost_env_variables(app, module=None, user=None):
    """
    Generate an environment variable dictionnary for fabric

    >>> sorted(get_ghost_env_variables({'name':'name', 'env':'env', 'role':'role', 'blue_green':{'test':''}}).items())
    [('GHOST_APP', 'name'), ('GHOST_ENV', 'env'), ('GHOST_ROLE', 'role')]

    >>> sorted(get_ghost_env_variables({'name':'name', 'env':'env', 'role':'role', 'blue_green':{'color':'blue'}}).items())
    [('GHOST_ACTIVE_COLOR', 'green'), ('GHOST_APP', 'name'), ('GHOST_ENV', 'env'), ('GHOST_ENV_COLOR', 'blue'), ('GHOST_ROLE', 'role')]

    >>> sorted(get_ghost_env_variables({'name':'name', 'env':'env', 'role':'role', 'blue_green':{'color':'blue', 'is_online': False}}).items())
    [('GHOST_ACTIVE_COLOR', 'green'), ('GHOST_APP', 'name'), ('GHOST_ENV', 'env'), ('GHOST_ENV_COLOR', 'blue'), ('GHOST_ROLE', 'role')]

    >>> sorted(get_ghost_env_variables({'name':'name', 'env':'env', 'role':'role', 'blue_green':{'color':'blue', 'is_online': True}}).items())
    [('GHOST_ACTIVE_COLOR', 'blue'), ('GHOST_APP', 'name'), ('GHOST_ENV', 'env'), ('GHOST_ENV_COLOR', 'blue'), ('GHOST_ROLE', 'role')]

    >>> sorted(get_ghost_env_variables({'name':'name', 'env':'env', 'role':'role'}, {'name':'name'}).items())
    [('GHOST_APP', 'name'), ('GHOST_ENV', 'env'), ('GHOST_ROLE', 'role')]

    >>> sorted(get_ghost_env_variables({'name':'name', 'env':'env', 'role':'role'}, {'name':'name', 'path':'path', 'git_repo':'git_repo'}).items())
    [('GHOST_APP', 'name'), ('GHOST_ENV', 'env'), ('GHOST_MODULE_NAME', 'name'), ('GHOST_MODULE_PATH', 'path'), ('GHOST_MODULE_REPO', 'git_repo'), ('GHOST_ROLE', 'role')]

    >>> sorted(get_ghost_env_variables({'name':'name', 'env':'env', 'role':'role'}, {'name':'name', 'path':'path', 'git_repo':'git_repo'}, 'user').items())
    [('GHOST_APP', 'name'), ('GHOST_ENV', 'env'), ('GHOST_MODULE_NAME', 'name'), ('GHOST_MODULE_PATH', 'path'), ('GHOST_MODULE_REPO', 'git_repo'), ('GHOST_MODULE_USER', 'user'), ('GHOST_ROLE', 'role')]

    >>> sorted(get_ghost_env_variables({'name':'name', 'env':'env', 'role':'role', 'env_vars':[{'var_key':'EMPTY_ENV'}]}).items())
    [('EMPTY_ENV', ''), ('GHOST_APP', 'name'), ('GHOST_ENV', 'env'), ('GHOST_ROLE', 'role')]

    >>> sorted(get_ghost_env_variables({'name':'name', 'env':'env', 'role':'role', 'env_vars':[{'var_key':'TEST_ENV', 'var_value':'VALUE'}]}).items())
    [('GHOST_APP', 'name'), ('GHOST_ENV', 'env'), ('GHOST_ROLE', 'role'), ('TEST_ENV', 'VALUE')]
    """
    ghost_env = {
        'GHOST_APP': app['name'],
        'GHOST_ENV': app['env'],
        'GHOST_ROLE': app['role'],
    }
    if app.get('blue_green', {}).get('color', None):
        inverted_colors = {"blue": "green", "green" : "blue"}
        color = app['blue_green']['color']
        ghost_env.update({
            'GHOST_ENV_COLOR': color,
            'GHOST_ACTIVE_COLOR': color if app['blue_green'].get('is_online', False) else inverted_colors[color]
        })
    if module and {'name', 'path', 'git_repo'} <= set(module):
        ghost_env['GHOST_MODULE_NAME'] = module['name']
        ghost_env['GHOST_MODULE_PATH'] = module['path']
        ghost_env['GHOST_MODULE_REPO'] = module['git_repo'].strip()
        if user:
            ghost_env['GHOST_MODULE_USER'] = user
    custom_env_vars = app.get('env_vars', None)
    if custom_env_vars and len(custom_env_vars):
        ghost_env.update({
            env_var['var_key'].encode('ascii', 'ignore'): env_var.get('var_value', '').encode('ascii', 'ignore')
            for env_var in custom_env_vars
        })
    return ghost_env


def get_mirror_path_from_module(app_module):
    """
    >>> app_module = {'git_repo': 'git@github.com:claranet/ghost.git'}
    >>> get_mirror_path_from_module(app_module)
    '/ghost/.mirrors/git@github.com:claranet/ghost.git'
    >>> app_module = {'git_repo': ' git@github.com:claranet/spaces.git '}
    >>> get_mirror_path_from_module(app_module)
    '/ghost/.mirrors/git@github.com:claranet/spaces.git'
    """
    return "/ghost/.mirrors/{remote}".format(remote=app_module['git_repo'].strip())


def get_lock_path_from_repo(git_repo):
    """
    >>> app_module = {'git_repo': 'git@github.com:claranet/ghost.git'}
    >>> get_lock_path_from_repo(app_module['git_repo'])
    '/ghost/.mirrors/.locks/git@github.com:claranet/ghost.git'
    >>> app_module = {'git_repo': ' git@github.com:claranet/spaces.git '}
    >>> get_lock_path_from_repo(app_module['git_repo'])
    '/ghost/.mirrors/.locks/git@github.com:claranet/spaces.git'
    """
    return "/ghost/.mirrors/.locks/{remote}".format(remote=git_repo.strip())


def get_local_repo_path(base_path, app_name, unique_id):
    return "{base}/{name}-{uid}".format(base=base_path, name=app_name, uid=unique_id)
