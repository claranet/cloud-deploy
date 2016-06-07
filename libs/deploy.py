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


def get_key_path(config, region, key_name):
    """
    Maps an AWS EC2 key pair name to a local private key path

        :param key_name: string: the name of the key as defined in AWS EC2 Key Pairs

    Without any configuration, an empty path is returned:

    >>> get_key_path({}, None, None)
    ''

    Given a configuration with a single key path for all EC2 instances in all regions:

    >>> config = {
    ...   'key_path': '/home/admin/key/morea.pem'
    ... }

    The same key path is returned, whatever the region or key name:

    >>> get_key_path(config, None, None)
    '/home/admin/key/morea.pem'
    >>> get_key_path(config, 'eu-west-1', None)
    '/home/admin/key/morea.pem'
    >>> get_key_path(config, 'eu-west-1', 'morea')
    '/home/admin/key/morea.pem'

    Given a configuration with a mapping from regions to key paths:

    >>> config = {
    ...   'key_path': {
    ...     'eu-west-1': '/home/admin/key/morea-eu-west-1.pem',
    ...     'us-west-2': '/home/admin/key/morea-us-west-2.pem'
    ...   }
    ... }

    The key path corresponding to the requested region is returned, whatever the key name:

    >>> get_key_path(config, 'eu-west-1', None)
    '/home/admin/key/morea-eu-west-1.pem'
    >>> get_key_path(config, 'eu-west-1', 'morea')
    '/home/admin/key/morea-eu-west-1.pem'
    >>> get_key_path(config, 'us-west-2', None)
    '/home/admin/key/morea-us-west-2.pem'
    >>> get_key_path(config, 'us-west-2', 'morea')
    '/home/admin/key/morea-us-west-2.pem'
    """

    key_path = config.get('key_path', '')
    if isinstance(key_path, dict):
        key_path = key_path[region]

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
    key_filename = get_key_path(config, app_region, app['environment_infos']['key_name'])
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
