import pkgutil

from flask import jsonify
from flask import Blueprint

from eve.auth import requires_auth
from libs import blue_green
from ghost_tools import boolify, config

commands_blueprint = Blueprint('commands_blueprint', __name__)


def _get_commands(with_fields=False):
    commands = []
    ghost_blue_green = blue_green.ghost_has_blue_green_enabled()
    for _, name, _ in pkgutil.iter_modules(['commands']):
        command = __import__('commands.' + name, fromlist=['COMMAND_DESCRIPTION', 'COMMAND_APP_FIELDS'])
        if not ghost_blue_green:
            # Blue/Green is disabled
            if name in blue_green.BLUE_GREEN_COMMANDS:
                continue
        # Check if `executescript` is disabled
        if name == 'executescript' and not boolify(config.get('enable_executescript_command', True)):
            continue
        if with_fields:
            commands.append( (name, command.COMMAND_APP_FIELDS) )
        else:
            commands.append( (name, command.COMMAND_DESCRIPTION) )
    return commands


@commands_blueprint.route('/commands', methods=['GET'])
def list_commands():
    """
    Returns a mapping of the available commands and their descriptions:

    >>> from web_ui.tests import create_test_app_context; create_test_app_context()
    >>> import json
    >>> blue_green.ghost_has_blue_green_enabled = lambda: False
    >>> config['enable_executescript_command'] = 'true'

    >>> sorted(json.loads(list_commands().data))
    [[u'buildimage', u'Build Image'], [u'createinstance', u'Create a new instance'], [u'deploy', u'Deploy module(s)'], [u'destroyallinstances', u'Destroy all instances'], [u'executescript', u'Execute a script/commands on every instance'], [u'recreateinstances', u'Recreate all the instances, rolling update possible when using an Autoscale'], [u'redeploy', u'Re-deploy an old module package'], [u'updateautoscaling', u'Update the autoscaling group and its LaunchConfiguration'], [u'updatelifecyclehooks', u'Update LifeCycle Hooks scripts']]

    >>> config['enable_executescript_command'] = 'false'
    >>> sorted(json.loads(list_commands().data))
    [[u'buildimage', u'Build Image'], [u'createinstance', u'Create a new instance'], [u'deploy', u'Deploy module(s)'], [u'destroyallinstances', u'Destroy all instances'], [u'recreateinstances', u'Recreate all the instances, rolling update possible when using an Autoscale'], [u'redeploy', u'Re-deploy an old module package'], [u'updateautoscaling', u'Update the autoscaling group and its LaunchConfiguration'], [u'updatelifecyclehooks', u'Update LifeCycle Hooks scripts']]

    >>> blue_green.ghost_has_blue_green_enabled = lambda: True
    >>> config['enable_executescript_command'] = 'true'
    >>> sorted(json.loads(list_commands().data))
    [[u'buildimage', u'Build Image'], [u'createinstance', u'Create a new instance'], [u'deploy', u'Deploy module(s)'], [u'destroyallinstances', u'Destroy all instances'], [u'executescript', u'Execute a script/commands on every instance'], [u'preparebluegreen', u'Prepare the Blue/Green env before swap'], [u'purgebluegreen', u'Purge the Blue/Green env'], [u'recreateinstances', u'Recreate all the instances, rolling update possible when using an Autoscale'], [u'redeploy', u'Re-deploy an old module package'], [u'swapbluegreen', u'Swap the Blue/Green env'], [u'updateautoscaling', u'Update the autoscaling group and its LaunchConfiguration'], [u'updatelifecyclehooks', u'Update LifeCycle Hooks scripts']]
    """
    return jsonify(_get_commands())


@commands_blueprint.route('/commands/fields', methods=['GET'])
def list_commands_app_fields_impact():
    """
    Returns a mapping of the available commands and which App's fields are used:

    >>> from web_ui.tests import create_test_app_context; create_test_app_context()
    >>> import json
    >>> blue_green.ghost_has_blue_green_enabled = lambda: False
    >>> config['enable_executescript_command'] = 'true'

    >>> sorted(json.loads(list_commands_app_fields_impact().data))
    [[u'buildimage', [u'features', u'build_infos']], [u'createinstance', [u'environment_infos']], [u'deploy', [u'modules']], [u'destroyallinstances', []], [u'executescript', []], [u'recreateinstances', []], [u'redeploy', []], [u'updateautoscaling', [u'autoscale', u'environment_infos']], [u'updatelifecyclehooks', [u'lifecycle_hooks']]]

    >>> config['enable_executescript_command'] = 'false'
    >>> sorted(json.loads(list_commands_app_fields_impact().data))
    [[u'buildimage', [u'features', u'build_infos']], [u'createinstance', [u'environment_infos']], [u'deploy', [u'modules']], [u'destroyallinstances', []], [u'recreateinstances', []], [u'redeploy', []], [u'updateautoscaling', [u'autoscale', u'environment_infos']], [u'updatelifecyclehooks', [u'lifecycle_hooks']]]

    >>> blue_green.ghost_has_blue_green_enabled = lambda: True
    >>> config['enable_executescript_command'] = 'true'
    >>> sorted(json.loads(list_commands_app_fields_impact().data))
    [[u'buildimage', [u'features', u'build_infos']], [u'createinstance', [u'environment_infos']], [u'deploy', [u'modules']], [u'destroyallinstances', []], [u'executescript', []], [u'preparebluegreen', [u'blue_green']], [u'purgebluegreen', [u'blue_green']], [u'recreateinstances', []], [u'redeploy', []], [u'swapbluegreen', [u'blue_green']], [u'updateautoscaling', [u'autoscale', u'environment_infos']], [u'updatelifecyclehooks', [u'lifecycle_hooks']]]
    """
    return jsonify(_get_commands(with_fields=True))
