import pkgutil
import os

from flask import abort, jsonify, send_from_directory
from flask import Blueprint

from ghost_tools import config, get_job_log_remote_path, CURRENT_REVISION
from ghost_aws import download_file_from_s3
from ghost_data import get_app, get_job

from settings import cloud_connections, DEFAULT_PROVIDER
from command import LOG_ROOT

commands_blueprint = Blueprint('commands_blueprint', 'commands')
version_blueprint = Blueprint('version_blueprint', 'version')
job_logs_blueprint = Blueprint('job_logs_blueprint', 'job_logs')


def _get_commands(app_context=None):
    commands = []
    for _, name, _ in pkgutil.iter_modules(['commands']):
        command = __import__('commands.' + name, fromlist=[
            'COMMAND_DESCRIPTION',
            'RELATED_APP_FIELDS',
            'is_available'
        ])
        if not command.is_available(app_context):
            continue
        commands.append( (name, command.COMMAND_DESCRIPTION, command.RELATED_APP_FIELDS) )
    return commands


@commands_blueprint.route('/commands', methods=['GET'])
@commands_blueprint.route('/commands/<app_id>', methods=['GET'])
def list_commands(app_id=None):
    """
    Returns a mapping of the available commands and their descriptions:

    >>> from tests.helpers import create_test_app_context; create_test_app_context()
    >>> import json
    >>> config['enable_executescript_command'] = 'true'
    >>> config['blue_green'] = {'enabled': True}

    >>> sorted(json.loads(list_commands().data))
    [[u'buildimage', u'Build Image'], [u'createinstance', u'Create a new instance'], [u'deploy', u'Deploy module(s)'], [u'destroyallinstances', u'Destroy all instances'], [u'executescript', u'Execute a script/commands on every instance'], [u'preparebluegreen', u'Prepare the Blue/Green env before swap'], [u'purgebluegreen', u'Purge the Blue/Green env'], [u'recreateinstances', u'Recreate all the instances, rolling update possible when using an Autoscale'], [u'redeploy', u'Re-deploy an old module package'], [u'swapbluegreen', u'Swap the Blue/Green env'], [u'updateautoscaling', u'Update the autoscaling group and its LaunchConfiguration'], [u'updatelifecyclehooks', u'Update LifeCycle Hooks scripts']]

    >>> config['enable_executescript_command'] = 'false'
    >>> sorted(json.loads(list_commands().data))
    [[u'buildimage', u'Build Image'], [u'createinstance', u'Create a new instance'], [u'deploy', u'Deploy module(s)'], [u'destroyallinstances', u'Destroy all instances'], [u'preparebluegreen', u'Prepare the Blue/Green env before swap'], [u'purgebluegreen', u'Purge the Blue/Green env'], [u'recreateinstances', u'Recreate all the instances, rolling update possible when using an Autoscale'], [u'redeploy', u'Re-deploy an old module package'], [u'swapbluegreen', u'Swap the Blue/Green env'], [u'updateautoscaling', u'Update the autoscaling group and its LaunchConfiguration'], [u'updatelifecyclehooks', u'Update LifeCycle Hooks scripts']]
    """
    app_context = get_app(app_id)
    return jsonify([(name, description) for (name, description, app_fields) in _get_commands(app_context)])


@commands_blueprint.route('/commands/fields', methods=['GET'])
@commands_blueprint.route('/commands/fields/<app_id>', methods=['GET'])
def list_commands_app_fields_impact(app_id=None):
    """
    Returns a mapping of the available commands and which App's fields are used:

    >>> from tests.helpers import create_test_app_context; create_test_app_context()
    >>> import json
    >>> config['enable_executescript_command'] = 'true'
    >>> config['blue_green'] = {'enabled': True}

    >>> sorted(json.loads(list_commands_app_fields_impact().data))
    [[u'buildimage', [u'features', u'build_infos']], [u'createinstance', [u'environment_infos']], [u'deploy', [u'modules']], [u'destroyallinstances', []], [u'executescript', []], [u'preparebluegreen', [u'blue_green']], [u'purgebluegreen', [u'blue_green']], [u'recreateinstances', [u'features', u'environment_infos']], [u'redeploy', []], [u'swapbluegreen', [u'blue_green']], [u'updateautoscaling', [u'autoscale', u'environment_infos']], [u'updatelifecyclehooks', [u'lifecycle_hooks']]]

    >>> config['enable_executescript_command'] = 'false'
    >>> sorted(json.loads(list_commands_app_fields_impact().data))
    [[u'buildimage', [u'features', u'build_infos']], [u'createinstance', [u'environment_infos']], [u'deploy', [u'modules']], [u'destroyallinstances', []], [u'preparebluegreen', [u'blue_green']], [u'purgebluegreen', [u'blue_green']], [u'recreateinstances', [u'features', u'environment_infos']], [u'redeploy', []], [u'swapbluegreen', [u'blue_green']], [u'updateautoscaling', [u'autoscale', u'environment_infos']], [u'updatelifecyclehooks', [u'lifecycle_hooks']]]
    """
    app_context = get_app(app_id)
    return jsonify([(name, app_fields) for (name, description, app_fields) in _get_commands(app_context)])


@version_blueprint.route('/version', methods=['GET'])
def get_version():
    """
    Return the current release revision, date and name

    >>> from tests.helpers import create_test_app_context; create_test_app_context()
    >>> import json

    >>> sorted(json.loads(get_version().data))
    [u'current_revision', u'current_revision_date', u'current_revision_name']
    """
    return jsonify(CURRENT_REVISION)


@job_logs_blueprint.route('/jobs/<regex("[a-f0-9]{24}"):job_id>/logs', methods=['GET'])
def job_logs(job_id=None):
    job = get_job(job_id)
    if job is None:
        abort(404, description='Specified job_id don\'t exist.')
    filename = os.path.join(LOG_ROOT, job_id + '.txt')
    if not os.path.isfile(filename):
        remote_log_path = get_job_log_remote_path(job_id)
        download_file_from_s3(cloud_connections.get(DEFAULT_PROVIDER)(None), config['bucket_s3'],
                              config['bucket_region'], remote_log_path, filename)
    if not os.path.isfile(filename):
        abort(404, description='No log file yet.')

    return send_from_directory(LOG_ROOT, job_id + '.txt', as_attachment=True)
