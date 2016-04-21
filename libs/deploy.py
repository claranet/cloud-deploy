from copy import copy

from fabric.api import execute as fab_execute
from fabfile import deploy

from ghost_tools import config
from ghost_tools import render_stage2
from ghost_log import log

def launch_deploy(app, module, hosts_list, fabric_execution_strategy, log_file):
    """ Launch fabric tasks on remote hosts.

        :param  app:          dict: Ghost object which describe the application parameters.
        :param  fabric_execution_strategy  string: Deployment strategy(serial or parrallel).
        :param  module:       dict: Ghost object which describe the module parameters.
        :param  hosts_list:   list: Instances private IP.
        :param  log_file:     object for logging.
    """
    key_filename = config.get('key_path', '')
    if isinstance(key_filename, dict):
        key_filename = key_filename[app['region']]
    app_ssh_username = app['build_infos']['ssh_username']
    bucket_region = config.get('bucket_region', app['region'])
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
