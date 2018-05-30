import hashlib
import hmac
import os
import random
import pkgutil

from eve.auth import requires_auth
from flask import abort, Blueprint, g, jsonify, request, send_from_directory
from eve.methods.post import post_internal

from hashlib import sha512
from command import LOG_ROOT
from ghost_aws import download_file_from_s3
from ghost_data import get_app, get_webhook
from ghost_data import get_job
from ghost_tools import config, CURRENT_REVISION
from ghost_tools import get_job_log_remote_path
from settings import cloud_connections, DEFAULT_PROVIDER

commands_blueprint = Blueprint('commands_blueprint', 'commands')
version_blueprint = Blueprint('version_blueprint', 'version')
job_logs_blueprint = Blueprint('job_logs_blueprint', 'job_logs')
websocket_token_blueprint = Blueprint('websocket_token_blueprint', 'websocket_token')
webhook_blueprint = Blueprint('webhook_blueprint', 'webhook')


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
@requires_auth('')
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
@requires_auth('')
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
@requires_auth('')
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
@requires_auth('')
def job_logs(job_id=None):
    job = get_job(job_id)
    if job is None:
        abort(404, description='Specified job_id doesn\'t exist.')
    filename = os.path.join(LOG_ROOT, job_id + '.txt')
    if not os.path.isfile(filename):
        remote_log_path = get_job_log_remote_path(job_id)
        download_file_from_s3(cloud_connections.get(DEFAULT_PROVIDER)(None), config['bucket_s3'],
                              config['bucket_region'], remote_log_path, filename)
    if not os.path.isfile(filename):
        abort(404, description='No log file yet.')

    return send_from_directory(LOG_ROOT, job_id + '.txt', as_attachment=True)


@websocket_token_blueprint.route('/jobs/<regex("[a-f0-9]{24}"):job_id>/websocket_token', methods=['GET'])
@requires_auth('')
def websocket_token(job_id=None):
    job = get_job(job_id)
    if job is None:
        abort(404, description='Specified job_id doesn\'t exist.')
    return jsonify({ 'token': get_websocket_token(job_id) })


def get_websocket_token(job_id):
    return sha512(websocket_token.hash_seed + job_id).hexdigest()

websocket_token.hash_seed = "%032x" % random.getrandbits(2048)

def get_webhook_rev(webhook, data):
    if webhook['vcs'] == 'github':
        return data['ref']

    if webhook['vcs'] == 'bitbucket':
        if webhook['event'] == 'repo:push':
            return data['push']['changes'][0]['new']['name']

    if webhook['vcs'] == 'gitlab':
        return data['ref']


def get_webhook_urls(webhook, data):
    if webhook['vcs'] == 'github':
        url_types = ['url', 'git_url', 'clone_url', 'ssh_url']
        return [data['repository'][url_type] for url_type in url_types]

    if webhook['vcs'] == 'bitbucket':
        urls = [data['repository']['links']['html']]

        if 'full_name' in data['repository']:
            name = data['repository']['full_name']
            urls.append('git@bitbucket.org:{name}.git'.format(name=name))
            urls.append('https://jorcau-claranet@bitbucket.org/{name}.git'.format(name=name))

        return urls

    if webhook['vcs'] == 'gitlab':
        url_types = ['url', 'git_http_url', 'git_ssh_url']
        return [data['repository'][url_type] for url_type in url_types]


def get_webhook_from_request():
    webhook = {
        'vcs': '',
        'event': '',
        'urls': [],
        'rev': '',
        'secret_token': ''
    }
    headers = request.headers
    data = request.get_json()

    # Create VCS configuration
    if 'GitHub' in headers['User-Agent']:
        vcs = {
            'name': 'github',
            'event': 'x-github-event',
            'secret_token': 'X-Hub-Signature'
        }
    elif 'GitLab' in headers['User-Agent']:
        vcs = {
            'name': 'gitlab',
            'event': 'x-gitlab-event',
            'secret_token': 'X-Gitlab-Token'
        }
    elif 'Bitbucket' in headers['User-Agent']:
        vcs = {
            'name': 'bitbucket',
            'event': 'X-Event-Key',
            'secret_token': 'Unavailable'
        }
    else:
        return None

    webhook['vcs'] = vcs['name']
    webhook['event'] = headers[vcs['event']]
    if vcs['secret_token'] in headers:
        webhook['secret_token'] = headers[vcs['secret_token']]
    webhook['rev'] = get_webhook_rev(webhook, data)
    webhook['urls'] = get_webhook_urls(webhook, data)

    return webhook


def validate_secret(conf_secret, webhook):
    if webhook['vcs'] == 'github':
        conf_token = "sha1=" + hmac.new(str(conf_secret),
                                        str(request.get_data(as_text=True)),
                                        hashlib.sha1).hexdigest()

        return conf_token == webhook['secret_token']

    if webhook['vcs'] == 'gitlab':
        return conf_secret == webhook['secret_token']


def validate_request(conf, webhook):
    # Check secret is valid if there's one
    if 'secret_token' in conf:
        if 'secret_token' not in webhook or not validate_secret(conf['secret_token'], webhook):
            return False, 'invalid secret token'

    # Check event is valid
    valid_event = False
    for event in conf['events']:
        if event in webhook['event']:
            valid_event = True
    if not valid_event:
        return False, 'no matching event'

    # Check rev is valid
    if webhook['rev'] not in [rev for rev in conf['revs']] and '*' not in conf['revs']:
        return False, 'no matching revision'

    # Check repo url
    try:
        app = get_app(conf['app_id'])
        valid_url = False
        for module in app['modules']:
            if module['name'] == conf['module'] and module['git_repo'] in webhook['urls']:
                valid_url = True
        if not valid_url:
            return False, 'no matching repository url'
    except Exception as e:
        return False, 'couldn\'t check repo: {err}'.format(err=e)

    return True, ''


@webhook_blueprint.route('/webhook/<webhook_id>', methods=['POST'])
def handle_webhook(webhook_id):
    """
    Checks webhook's validity and runs desired commands.
    """
    # Get webhook conf from ID
    webhook_conf = get_webhook(webhook_id)
    if not webhook_conf:
        abort(404, 'could not find webhook Cloud Deploy configuration matching webhook request: {id}.'.format(id=webhook_id))

    # Standardises webhook payload information
    webhook_request = get_webhook_from_request()
    if webhook_request is None:
        abort(422, 'invalid webhook request payload.'.format(id=webhook_id))

    # Checks configuration matches payload
    validated, err = validate_request(webhook_conf, webhook_request)
    if not validated:
        abort(403, 'webhook request doesn\'t match its Cloud Deploy configuration: {id}. error: {err}.'.format(id=webhook_id, err=err))

    # Create job configuration
    job_config = {
        'app_id': webhook_conf['app_id'],
    }
    if 'safe_deployment_strategy' in webhook_conf:
        job_config['safe_deployment_strategy'] = webhook_conf['safe_deployment_strategy']
    if 'module' in webhook_conf:
        job_config['modules'] = [{
            'name': webhook_conf['module'],
            'rev': str(webhook_request['rev'])
        }]
    if 'instance_type' in webhook_conf:
        job_config['instance_type'] = webhook_conf['instance_type']

    g.user = 'webhook_' + str(webhook_id)

    # Launches desired jobs
    for command in set(webhook_conf['commands']):
        job_config['command'] = command
        job, _, _, rc, _ = post_internal('jobs', job_config)
        if rc >= 400:
            abort(500, 'webhook {id} failed to start job: {err}'.format(id=webhook_id, err=job))

    return 'Webhook received! The job {id} has been created.\n\nJob details: {job}'.format(id=str(job['_id']), job=str(job))
