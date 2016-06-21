"""

"""
# -*- coding: utf-8 -*-
#!/usr/bin/env python

from copy import copy
from fabric.api import execute as fab_execute
from fabfile import deploy
from ghost_tools import config
from ghost_tools import render_stage2
from ghost_log import log
from settings import cloud_connections, DEFAULT_PROVIDER
from ghost_tools import GCallException

def get_path_from_app(app):
    """
    >>> get_path_from_app({'name': 'AppName', 'env': 'prod', 'role': 'webfront'})
    '/ghost/AppName/prod/webfront'
    """
    return "/ghost/{name}/{env}/{role}".format(name=app['name'], env=app['env'], role=app['role'])

def get_path_from_app_with_color(app):
    """
    >>> get_path_from_app_with_color({'name': 'AppName', 'env': 'prod', 'role': 'webfront', 'blue_green': {'color': 'blue'}})
    '/ghost/AppName/prod/webfront/blue'
    """
    if 'blue_green' in app and 'color' in app['blue_green']:
        return "/ghost/{name}/{env}/{role}/{color}".format(name=app['name'], env=app['env'],
                                                           role=app['role'], color=app['blue_green']['color'])
    else:
        return get_path_from_app(app)

def update_app_manifest(app, config, module, package, log_file):
    """
    Update the app manifest into S3
    """
    key_path = get_path_from_app_with_color(app) + '/MANIFEST'
    cloud_connection = cloud_connections.get(app.get('provider', DEFAULT_PROVIDER))(log_file)
    conn = cloud_connection.get_connection(config.get('bucket_region', app['region']), ["s3"])
    bucket = conn.get_bucket(config['bucket_s3'])
    key = bucket.get_key(key_path)
    modules = []
    module_exist = False
    all_app_modules_list = get_app_module_name_list(app['modules'])
    data = ""
    if not key: # if the 'colored' MANIFEST doesn't' exist, maybe the legacy one exists and we should clone it
        legacy_key_path = get_path_from_app(app) + '/MANIFEST'
        legacy_key = bucket.get_key(key_path)
        if legacy_key:
            key = legacy_key.copy(bucket, key_path)
    if key:
        manifest = key.get_contents_as_string()
        if sys.version > '3':
            manifest = manifest.decode('utf-8')
        for line in manifest.split('\n'):
            if line:
                mod = {}
                tmp = line.split(':')
                mod['name'] = tmp[0]
                if mod['name'] == module['name']:
                    mod['package'] = package
                    mod['path'] = module['path']
                    module_exist = True
                else:
                    mod['package'] = tmp[1]
                    mod['path'] = tmp[2]
                # Only keep modules that have not been removed from the app
                if mod['name'] in all_app_modules_list:
                    mod['index'] = all_app_modules_list.index(mod['name'])
                    modules.append(mod)
    if not key:
        key = bucket.new_key(key_path)
    if not module_exist:
        modules.append({
            'name': module['name'],
            'package': package,
            'path': module['path'],
            'index': all_app_modules_list.index(module['name'])
        })
    for mod in sorted(modules, key=lambda mod: mod['index']):
        data = data + mod['name'] + ':' + mod['package'] + ':' + mod['path'] + '\n'
    manifest, manifest_path = tempfile.mkstemp()
    if sys.version > '3':
        os.write(manifest, bytes(data, 'UTF-8'))
    else:
        os.write(manifest, data)
    os.close(manifest)
    key.set_contents_from_filename(manifest_path)
    os.remove(manifest_path)


def get_key_path(config, region, account, key_name, log_file):
    """
    Maps an AWS EC2 key pair name to a local private key path

        :param key_name: string: the name of the key as defined in AWS EC2 Key Pairs

    Without any configuration, an empty path is returned:

    >>> from StringIO import StringIO
    >>> import yaml

    >>> get_key_path({}, None, None, None, StringIO())
    ''

    Given a configuration with a single key path for all EC2 instances in all regions:

    >>> config = yaml.load(\"\"\"
    ... key_path: /home/admin/key/morea.pem
    ... \"\"\")

    The same key path is returned, whatever the region or key name:

    >>> get_key_path(config, None, None, None, StringIO())
    '/home/admin/key/morea.pem'
    >>> get_key_path(config, 'eu-west-1', 'account', None, StringIO())
    '/home/admin/key/morea.pem'
    >>> get_key_path(config, 'eu-west-1', 'account', 'morea', StringIO())
    '/home/admin/key/morea.pem'

    Given a configuration with a mapping from regions to key paths:

    >>> config = yaml.load(\"\"\"
    ... key_path:
    ...   eu-west-1: /home/admin/key/morea-eu-west-1.pem
    ...   us-west-2: /home/admin/key/morea-us-west-2.pem
    ... \"\"\")

    The key path corresponding to the requested region is returned, whatever the key name:

    >>> get_key_path(config, 'eu-west-1', 'account', None, StringIO())
    '/home/admin/key/morea-eu-west-1.pem'
    >>> get_key_path(config, 'eu-west-1', 'account', 'morea', StringIO())
    '/home/admin/key/morea-eu-west-1.pem'
    >>> get_key_path(config, 'us-west-2', 'account', None, StringIO())
    '/home/admin/key/morea-us-west-2.pem'
    >>> get_key_path(config, 'us-west-2', 'account', 'morea', StringIO())
    '/home/admin/key/morea-us-west-2.pem'

    If a mapping is missing, an empty key path is returned:

    >>> get_key_path(config, 'us-west-1', 'account', 'morea', StringIO())
    ''

    Given a configuration with mappings from regions to accounts to key paths:

    >>> config = yaml.load(\"\"\"
    ... key_path:
    ...   eu-west-1:
    ...     '123456789': /home/admin/key/morea-account-1-eu-west-1.pem
    ...     '987654321': /home/admin/key/morea-account-2-eu-west-1.pem
    ...   us-west-2:
    ...     '123456789': /home/admin/key/morea-account-1-us-west-2.pem
    ...     '987654321': /home/admin/key/morea-account-2-us-west-2.pem
    ... \"\"\")

    The key path corresponding to the requested region and account is returned:

    >>> get_key_path(config, 'eu-west-1', '123456789', 'morea-key', StringIO())
    '/home/admin/key/morea-account-1-eu-west-1.pem'
    >>> get_key_path(config, 'eu-west-1', '987654321', 'morea-key', StringIO())
    '/home/admin/key/morea-account-2-eu-west-1.pem'
    >>> get_key_path(config, 'us-west-2', '123456789', 'morea-key', StringIO())
    '/home/admin/key/morea-account-1-us-west-2.pem'
    >>> get_key_path(config, 'us-west-2', '987654321', 'morea-key', StringIO())
    '/home/admin/key/morea-account-2-us-west-2.pem'

    If a mapping is missing, an empty key path is returned:

    >>> get_key_path(config, 'us-west-2', 'morea-account-3', 'morea-key', StringIO())
    ''
    >>> get_key_path(config, 'us-west-1', 'morea-123456789', 'morea-key', StringIO())
    ''

    Given a configuration with mappings from regions to accounts to key names to key paths:

    >>> config = yaml.load(\"\"\"
    ... key_path:
    ...   eu-west-1:
    ...     default:
    ...       morea-key-1: /home/admin/key/morea-default-key-1-eu-west-1.pem
    ...       morea-key-2: /home/admin/key/morea-default-key-2-eu-west-1.pem
    ...     # Account 1
    ...     '123456789':
    ...       morea-key-1: /home/admin/key/morea-account-1-key-1-eu-west-1.pem
    ...       morea-key-2: /home/admin/key/morea-account-1-key-2-eu-west-1.pem
    ...     # Account 2
    ...     '987654321':
    ...       morea-key-1: /home/admin/key/morea-account-2-key-1-eu-west-1.pem
    ...       morea-key-2: /home/admin/key/morea-account-2-key-2-eu-west-1.pem
    ...   us-west-2:
    ...     default:       /home/admin/key/morea-default-us-west-2.pem
    ...     # Account 1
    ...     '123456789':
    ...       morea-key-1: /home/admin/key/morea-account-1-key-1-us-west-2.pem
    ...       morea-key-2: /home/admin/key/morea-account-1-key-2-us-west-2.pem
    ...     '987654321':
    ...       morea-key-1: /home/admin/key/morea-account-2-key-1-us-west-2.pem
    ...       morea-key-2: /home/admin/key/morea-account-2-key-2-us-west-2.pem
    ... \"\"\")

    The key path corresponding to the requested region, account and key name is returned:

    >>> get_key_path(config, 'eu-west-1', '123456789', 'morea-key-1', StringIO())
    '/home/admin/key/morea-account-1-key-1-eu-west-1.pem'
    >>> get_key_path(config, 'eu-west-1', '123456789', 'morea-key-2', StringIO())
    '/home/admin/key/morea-account-1-key-2-eu-west-1.pem'
    >>> get_key_path(config, 'us-west-2', '987654321', 'morea-key-1', StringIO())
    '/home/admin/key/morea-account-2-key-1-us-west-2.pem'
    >>> get_key_path(config, 'us-west-2', '987654321', 'morea-key-2', StringIO())
    '/home/admin/key/morea-account-2-key-2-us-west-2.pem'

    If a mapping is missing, an empty key path is returned:

    >>> get_key_path(config, 'us-west-1', '666666666', 'morea-key-1', StringIO())
    ''
    >>> get_key_path(config, 'us-west-1', '123456789', 'morea-key-3', StringIO())
    ''

    Defaults are also available in case no assumed account id is defined on the Ghost application:

    >>> get_key_path(config, 'eu-west-1', '', 'morea-key-1', StringIO())
    '/home/admin/key/morea-default-key-1-eu-west-1.pem'
    >>> get_key_path(config, 'eu-west-1', '', 'morea-key-2', StringIO())
    '/home/admin/key/morea-default-key-2-eu-west-1.pem'
    >>> get_key_path(config, 'us-west-2', '', 'morea-key-3', StringIO())
    '/home/admin/key/morea-default-us-west-2.pem'
    """

    key_path = config.get('key_path', '')
    if isinstance(key_path, dict):
        key_path = key_path.get(region, '')
        if isinstance(key_path, dict):
            key_path = key_path.get(account if account else 'default', '')
            if isinstance(key_path, dict):
                key_path = key_path.get(key_name, '')

    # Uncomment the following line for debugging purposes locally (do not commit this change)
    #log("Selected '{}' key path for '{}' keypair name in '{}' region of '{}' account".format(key_path, key_name, region, account), log_file)

    return key_path

def launch_deploy(app, module, hosts_list, fabric_execution_strategy, log_file):
    """ Launch fabric tasks on remote hosts.

        :param  app:          dict: Ghost object which describe the application parameters.
        :param  fabric_execution_strategy  string: Deployment strategy(serial or parallel).
        :param  module:       dict: Ghost object which describe the module parameters.
        :param  hosts_list:   list: Instances private IP.
        :param  log_file:     object for logging.
    """
    app_region = app['region']
    app_assumed_account_id = app.get('assumed_account_id', '')

    # FIXME: key_name and ssh_username should be dynamically retrieved from each EC2 instance.
    # Indeed, in case of mixed deployments they may differ from one to another.
    # This can happen when these values are changed on the Ghost app but not all live instances are replaced to use the new values.
    app_key_name = app['environment_infos']['key_name']
    app_ssh_username = app['build_infos']['ssh_username']

    key_filename = get_key_path(config, app_region, app_assumed_account_id, app_key_name, log_file)

    bucket_region = config.get('bucket_region', app_region)
    stage2 = render_stage2(config, bucket_region)
    if fabric_execution_strategy not in ['serial', 'parallel']:
        fabric_execution_strategy = config.get('fabric_execution_strategy', 'serial')

    # Clone the deploy task function to avoid modifying the original shared instance
    task = copy(deploy)

    if fabric_execution_strategy == 'parallel':
        setattr(task, 'serial', False)
        setattr(task, 'parallel', True)
    else:
        setattr(task, 'serial', True)
        setattr(task, 'parallel', False)

    log("Updating current instances in {}: {}".format(fabric_execution_strategy, hosts_list), log_file)
    result = fab_execute(task, module, app_ssh_username, key_filename, stage2, log_file, hosts=hosts_list)
    hosts_error = []
    for host, ret_code in result.iteritems():
        if ret_code != 0:
            hosts_error.append(host)
    if len(hosts_error):
        raise GCallException("Deploy error on: %s" % (", ".join(hosts_error)))


