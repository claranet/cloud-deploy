import pkgutil

from flask import jsonify
from flask import Blueprint

from eve.auth import requires_auth

commands_blueprint = Blueprint('commands_blueprint', __name__)

@commands_blueprint.route('/commands', methods=['GET'])
def list_commands():
    """
    Returns a mapping of the available commands and their descriptions:

    >>> from web_ui.tests import create_test_app_context; create_test_app_context()
    >>> import json
    >>> sorted(json.loads(list_commands().data).items())
    [(u'buildimage', u'Build Image'), (u'createinstance', u'Create a new instance'), (u'deploy', u'Deploy module(s)'), (u'destroyallinstances', u'Destroy all instances'), (u'preparebluegreen', u'Prepare the Blue/Green env before swap'), (u'purgebluegreen', u'Purge the Blue/Green env'), (u'redeploy', u'Re-deploy an old module package'), (u'swapbluegreen', u'Swap the Blue/Green env'), (u'updateautoscaling', u'Update the autoscaling group and its LaunchConfiguration'), (u'updatelifecyclehooks', u'Update LifeCycle Hooks scripts')]
    """
    commands = []
    for _, name, _ in pkgutil.iter_modules(['commands']):
        command = __import__('commands.' + name, fromlist=['COMMAND_DESCRIPTION'])
        module_desc = command.COMMAND_DESCRIPTION
        commands.append( (name, module_desc) )
    return jsonify(commands)
