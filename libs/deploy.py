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


def get_key_path(config, region, account, key_name):
    """
    Maps an AWS EC2 key pair name to a local private key path

        :param key_name: string: the name of the key as defined in AWS EC2 Key Pairs

    Without any configuration, an empty path is returned:

    >>> get_key_path({}, None, None, None)
    ''

    Given a configuration with a single key path for all EC2 instances in all regions:

    >>> config = {
    ...   'key_path': '/home/admin/key/morea.pem'
    ... }

    The same key path is returned, whatever the region or key name:

    >>> get_key_path(config, None, None, None)
    '/home/admin/key/morea.pem'
    >>> get_key_path(config, 'eu-west-1', 'account', None)
    '/home/admin/key/morea.pem'
    >>> get_key_path(config, 'eu-west-1', 'account', 'morea')
    '/home/admin/key/morea.pem'

    Given a configuration with a mapping from regions to key paths:

    >>> config = {
    ...   'key_path': {
    ...     'eu-west-1': '/home/admin/key/morea-eu-west-1.pem',
    ...     'us-west-2': '/home/admin/key/morea-us-west-2.pem',
    ...   }
    ... }

    The key path corresponding to the requested region is returned, whatever the key name:

    >>> get_key_path(config, 'eu-west-1', 'account', None)
    '/home/admin/key/morea-eu-west-1.pem'
    >>> get_key_path(config, 'eu-west-1', 'account', 'morea')
    '/home/admin/key/morea-eu-west-1.pem'
    >>> get_key_path(config, 'us-west-2', 'account', None)
    '/home/admin/key/morea-us-west-2.pem'
    >>> get_key_path(config, 'us-west-2', 'account', 'morea')
    '/home/admin/key/morea-us-west-2.pem'

    If a mapping is missing, an empty key path is returned:

    >>> get_key_path(config, 'us-west-1', 'account', 'morea')
    ''

    Given a configuration with mappings from regions to accounts to key paths:

    >>> config = {
    ...   'key_path': {
    ...     'eu-west-1': {
    ...       '123456789': '/home/admin/key/morea-account-1-eu-west-1.pem',
    ...       '987654321': '/home/admin/key/morea-account-2-eu-west-1.pem',
    ...     },
    ...     'us-west-2': {
    ...       '123456789': '/home/admin/key/morea-account-1-us-west-2.pem',
    ...       '987654321': '/home/admin/key/morea-account-2-us-west-2.pem',
    ...     }
    ...   }
    ... }

    The key path corresponding to the requested region and account is returned:

    >>> get_key_path(config, 'eu-west-1', '123456789', 'morea-key')
    '/home/admin/key/morea-account-1-eu-west-1.pem'
    >>> get_key_path(config, 'eu-west-1', '987654321', 'morea-key')
    '/home/admin/key/morea-account-2-eu-west-1.pem'
    >>> get_key_path(config, 'us-west-2', '123456789', 'morea-key')
    '/home/admin/key/morea-account-1-us-west-2.pem'
    >>> get_key_path(config, 'us-west-2', '987654321', 'morea-key')
    '/home/admin/key/morea-account-2-us-west-2.pem'

    If a mapping is missing, an empty key path is returned:

    >>> get_key_path(config, 'us-west-2', 'morea-account-3', 'morea-key')
    ''
    >>> get_key_path(config, 'us-west-1', 'morea-123456789', 'morea-key')
    ''

    Given a configuration with mappings from regions to accounts to key names to key paths:

    >>> config = {
    ...   'key_path': {
    ...     'eu-west-1': {
    ...       # Account 1
    ...       '123456789': {
    ...         'morea-key-1': '/home/admin/key/morea-account-1-key-1-eu-west-1.pem',
    ...         'morea-key-2': '/home/admin/key/morea-account-1-key-2-eu-west-1.pem',
    ...       },
    ...       # Account 2
    ...       '987654321': {
    ...         'morea-key-1': '/home/admin/key/morea-account-2-key-1-eu-west-1.pem',
    ...         'morea-key-2': '/home/admin/key/morea-account-2-key-2-eu-west-1.pem',
    ...       }
    ...     },
    ...     'us-west-2': {
    ...       # Account 1
    ...       '123456789': {
    ...         'morea-key-1': '/home/admin/key/morea-account-1-key-1-us-west-2.pem',
    ...         'morea-key-2': '/home/admin/key/morea-account-1-key-2-us-west-2.pem',
    ...       },
    ...       '987654321': {
    ...         'morea-key-1': '/home/admin/key/morea-account-2-key-1-us-west-2.pem',
    ...         'morea-key-2': '/home/admin/key/morea-account-2-key-2-us-west-2.pem',
    ...       }
    ...     }
    ...   }
    ... }

    The key path corresponding to the requested region, account and key name is returned:

    >>> get_key_path(config, 'eu-west-1', '123456789', 'morea-key-1')
    '/home/admin/key/morea-account-1-key-1-eu-west-1.pem'
    >>> get_key_path(config, 'eu-west-1', '123456789', 'morea-key-2')
    '/home/admin/key/morea-account-1-key-2-eu-west-1.pem'
    >>> get_key_path(config, 'us-west-2', '987654321', 'morea-key-1')
    '/home/admin/key/morea-account-2-key-1-us-west-2.pem'
    >>> get_key_path(config, 'us-west-2', '987654321', 'morea-key-2')
    '/home/admin/key/morea-account-2-key-2-us-west-2.pem'

    If a mapping is missing, an empty key path is returned:

    >>> get_key_path(config, 'us-west-1', '666666666', 'morea-key-1')
    ''
    >>> get_key_path(config, 'us-west-1', '123456789', 'morea-key-3')
    ''
    """

    key_path = config.get('key_path', '')
    if isinstance(key_path, dict):
        key_path = key_path.get(region, '')
        if isinstance(key_path, dict):
            key_path = key_path.get(account, '')
            if isinstance(key_path, dict):
                key_path = key_path.get(key_name, '')

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
    key_filename = get_key_path(config, app_region, app_assumed_account_id, app['environment_infos']['key_name'])
    app_ssh_username = app['build_infos']['ssh_username']
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
    fab_execute(task, module, app_ssh_username, key_filename, stage2, log_file, hosts=hosts_list)
