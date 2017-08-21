import pkgutil

from flask import jsonify
from flask import Blueprint

from ghost_tools import config
from ghost_data import get_app

commands_blueprint = Blueprint('commands_blueprint', __name__)


def _get_commands(app_context=None):
    commands = []
    for _, name, _ in pkgutil.iter_modules(['commands']):
        command = __import__('commands.' + name, fromlist=[
            'COMMAND_DESCRIPTION',
            'RELATED_APP_FIELDS',
            'is_available_for_current_application'
        ])
        if not command.is_available_for_current_application(app_context):
            continue
        commands.append( (name, command.COMMAND_DESCRIPTION, command.RELATED_APP_FIELDS) )
    return commands


@commands_blueprint.route('/commands', methods=['GET'])
@commands_blueprint.route('/commands/<app_id>', methods=['GET'])
def list_commands(app_id=None):
    """
    Returns a mapping of the available commands and their descriptions:

    >>> from web_ui.tests import create_test_app_context; create_test_app_context()
    >>> import json
    >>> config['enable_executescript_command'] = 'true'

    >>> sorted(json.loads(list_commands().data))
    [[u'buildimage', u'Build Image'], [u'deploy', u'Deploy module(s)'], [u'destroyallinstances', u'Destroy all instances'], [u'executescript', u'Execute a script/commands on every instance'], [u'recreateinstances', u'Recreate all the instances, rolling update possible when using an Autoscale'], [u'redeploy', u'Re-deploy an old module package'], [u'updatelifecyclehooks', u'Update LifeCycle Hooks scripts']]

    >>> config['enable_executescript_command'] = 'false'
    >>> sorted(json.loads(list_commands().data))
    [[u'buildimage', u'Build Image'], [u'deploy', u'Deploy module(s)'], [u'destroyallinstances', u'Destroy all instances'], [u'recreateinstances', u'Recreate all the instances, rolling update possible when using an Autoscale'], [u'redeploy', u'Re-deploy an old module package'], [u'updatelifecyclehooks', u'Update LifeCycle Hooks scripts']]
    """
    app_context = get_app(app_id)
    return jsonify([(name, description) for (name, description, app_fields) in _get_commands(app_context)])


@commands_blueprint.route('/commands/fields', methods=['GET'])
def list_commands_app_fields_impact():
    """
    Returns a mapping of the available commands and which App's fields are used:

    >>> from web_ui.tests import create_test_app_context; create_test_app_context()
    >>> import json
    >>> config['enable_executescript_command'] = 'true'

    >>> sorted(json.loads(list_commands_app_fields_impact().data))
    [[u'buildimage', [u'features', u'build_infos']], [u'deploy', [u'modules']], [u'destroyallinstances', []], [u'executescript', []], [u'recreateinstances', []], [u'redeploy', []], [u'updatelifecyclehooks', [u'lifecycle_hooks']]]

    >>> config['enable_executescript_command'] = 'false'
    >>> sorted(json.loads(list_commands_app_fields_impact().data))
    [[u'buildimage', [u'features', u'build_infos']], [u'deploy', [u'modules']], [u'destroyallinstances', []], [u'recreateinstances', []], [u'redeploy', []], [u'updatelifecyclehooks', [u'lifecycle_hooks']]]
    """
    return jsonify([(name, app_fields) for (name, description, app_fields) in _get_commands()])
