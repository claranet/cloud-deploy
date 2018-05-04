"""
    Library with all needed functions by Ghost API
"""
# -*- coding: utf-8 -*-

import os
import binascii
from datetime import datetime
from eve.methods.post import post_internal
from ghost_tools import ghost_app_object_copy, get_available_provisioners_from_config, b64decode_utf8
from libs.blue_green import get_blue_green_from_app

OPPOSITE_COLOR = {
    'blue': 'green',
    'green': 'blue'
}
FORBIDDEN_PATH = ['/', '/tmp', '/var', '/etc', '/ghost', '/root', '/home', '/home/admin']
COMMAND_FIELDS = ['autoscale', 'blue_green', 'build_infos', 'environment_infos', 'lifecycle_hooks']
ALL_COMMAND_FIELDS = ['modules', 'features'] + COMMAND_FIELDS


class GhostAPIInputError(Exception):
    """Exception raised for errors in the input.

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message


def field_has_changed(new, old):
    """
    Returns true if the field has changed.
    Considers a None value equivalent to an empty string.

    >>> field_has_changed(1, 1)
    False
    >>> field_has_changed("a", "a")
    False
    >>> field_has_changed("", None)
    False
    >>> field_has_changed([], [])
    False
    >>> field_has_changed(0, None)
    True
    >>> field_has_changed("", [])
    True
    >>> field_has_changed("", False)
    True
    >>> field_has_changed({}, None)
    True
    """
    equivalents = [None, ""]
    return (new != old and
            (not new in equivalents or not old in equivalents))


def ghost_api_bluegreen_is_enabled(app):
    """
    Return if the Ghost app has Blue/green option enabled
    """
    blue_green = app.get('blue_green', None)
    return blue_green and blue_green.get('enable_blue_green', None)


def ghost_api_check_green_app_exists(apps_db, app):
    """
    Check if the Alter Ego application exists
    ie: the blue one or the green one (depending of the current app color)
    """
    name = app.get('name')
    role = app.get('role')
    env = app.get('env')
    blue_green, color = get_blue_green_from_app(app)
    if not color:
        color = 'blue'  # handle default one
    green_app = apps_db.find_one({'$and': [
        {'name': name},
        {'role': role},
        {'env': env},
        {'blue_green.color': OPPOSITE_COLOR[color]}
    ]})
    return green_app


def ghost_api_clean_bluegreen_app(apps_db, app):
    """
    Removes the 'blue_green' document from the current app
    """
    orig_bluegreen_conf = app.get('blue_green')

    if orig_bluegreen_conf:
        update_res = apps_db.update_one({'_id': app['_id']}, {'$unset': {'blue_green': ''}})
        if not update_res.matched_count == 1:  # if success, 1 row has been updated
            return False

    return True


def ghost_api_create_green_app(apps_db, app, user):
    """
    Create the Alter Ego application based on a copy of the current application
    with the opposite color and with _id relation updated
    """
    # Generate the BlueScreen object for the green app
    blue_green_source = app.get('blue_green')
    color = blue_green_source.get('color', 'blue') if blue_green_source else 'blue'

    # Create the green app and return its ID
    green_app = ghost_app_object_copy(app, user)
    green_app['blue_green'] = {}
    green_app['blue_green']['color'] = OPPOSITE_COLOR[color]

    green_app_db = post_internal('apps', green_app)

    if green_app_db[0]['_status'] == 'ERR':  # _status == OK when insert done by Eve
        print "ERROR when creating Green app for %s" % app['_id']
        print green_app_db
        return None

    # Set blue-green params to the Green app
    blue_green = {
        'enable_blue_green': True,
        'color': OPPOSITE_COLOR[color],
        'is_online': False,
        'alter_ego_id': app['_id']
    }

    update_res = apps_db.update_one({'_id': green_app_db[0]['_id']}, {'$set': {'blue_green': blue_green}})
    update_res_ami = update_res
    if 'ami' in app and 'build_infos' in app and 'ami_name' in app['build_infos']:  # Keep baked AMI too on green app
        ami_name = app['build_infos']['ami_name']
        update_res_ami = apps_db.update_one({'_id': green_app_db[0]['_id']},
                                            {'$set': {'ami': app['ami'], 'build_infos.ami_name': ami_name}})
    if update_res.matched_count == 1 and update_res_ami.matched_count == 1:
        return green_app_db[0]['_id']
    else:
        print update_res
        return None


def ghost_api_update_bluegreen_app(apps_db, blue_app, green_app_id):
    """
    Update the current app blue_green object
    """
    # Generate the BlueScreen object for the green app
    blue_green = blue_app.get('blue_green')
    color = blue_green.get('color', 'blue') if blue_green else 'blue'
    blue_green = {
        'enable_blue_green': True,
        'color': color,
        'is_online': True,
        'alter_ego_id': green_app_id
    }
    update_res = apps_db.update_one({'_id': blue_app['_id']}, {'$set': {'blue_green': blue_green}})
    return update_res.matched_count == 1


def ghost_api_enable_green_app(apps_db, app, user):
    """
    Main function that checks if Blue/Green is already enable
    If not, create the Green associated app
    """
    green_app = ghost_api_check_green_app_exists(apps_db, app)
    if not green_app:
        green_app_id = ghost_api_create_green_app(apps_db, app, user)
        if not green_app_id:
            return False
        else:
            return ghost_api_update_bluegreen_app(apps_db, app, green_app_id)
    else:
        return ghost_api_update_bluegreen_app(apps_db, app, green_app['_id'])


def ghost_api_delete_alter_ego_app(apps_db, app):
    """
    Delete the other app (blue or green) when blue green is enabled on the current targeted app
    """
    blue_green = app.get('blue_green', None)
    if blue_green and blue_green.get('alter_ego_id'):
        alter_app = apps_db.find_one({'$and': [
            {'_id': blue_green.get('alter_ego_id')}
        ]})
        if alter_app:
            # delete_internal('apps', ) -- doesn't exists in Eve for now :(
            return apps_db.delete_one({'_id': blue_green.get('alter_ego_id')}).deleted_count == 1
    return True


def check_app_feature_provisioner(updates):
    """
    Check if all provisioner choosen per feature is a valid one available in the core configuration
    """
    if 'features' in updates:
        provisioners_available = get_available_provisioners_from_config()
        for ft in updates['features']:
            if 'provisioner' in ft and not ft['provisioner'] in provisioners_available:
                raise GhostAPIInputError(
                    'Provisioner "{p}" set for feature "{f}" is not available or not compatible.'.format(
                        p=ft['provisioner'], f=ft['name']))


def check_app_module_path(updates):
    """
    Check if all modules path are allowed
    :param updates: Modules configurations

    >>> check_app_module_path({})

    >>> check_app_module_path({'modules': []})

    >>> check_app_module_path({'modules': [{'name': 'empty'}]})
    Traceback (most recent call last):
    ...
    GhostAPIInputError

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/tmp/test'}, {'name': 'mod2', 'path': '/srv/ok'}]}
    >>> check_app_module_path(app)

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/tmp/test/'}, {'name': 'mod2', 'path': '/srv/ok//'}]}
    >>> check_app_module_path(app)

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/tmp/'}, {'name': 'mod2', 'path': '/srv/ok//'}]}
    >>> check_app_module_path(app)
    Traceback (most recent call last):
    ...
    GhostAPIInputError

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/'}, {'name': 'mod2', 'path': '/srv/ok//'}]}
    >>> check_app_module_path(app)
    Traceback (most recent call last):
    ...
    GhostAPIInputError

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/ghost/x'}, {'name': 'mod2', 'path': '/ghost'}]}
    >>> check_app_module_path(app)
    Traceback (most recent call last):
    ...
    GhostAPIInputError

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/ghost/x'}, {'name': 'mod2', 'path': '/ghost////'}]}
    >>> check_app_module_path(app)
    Traceback (most recent call last):
    ...
    GhostAPIInputError

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/root/x/..'}, {'name': 'mod2', 'path': '/srv/ok'}]}
    >>> check_app_module_path(app)
    Traceback (most recent call last):
    ...
    GhostAPIInputError

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/root/x/.//'}, {'name': 'mod2', 'path': '/srv/ok'}]}
    >>> check_app_module_path(app)

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/root/x/.//..//////'}, {'name': 'mod2', 'path': '/srv/ok'}]}
    >>> check_app_module_path(app)
    Traceback (most recent call last):
    ...
    GhostAPIInputError
    """
    if 'modules' in updates:
        for mod in updates['modules']:
            if not 'path' in mod:
                raise GhostAPIInputError('Module "{m} has path empty"'.format(m=mod['name']))
            if os.path.abspath(mod['path']) in FORBIDDEN_PATH:
                raise GhostAPIInputError(
                    'Module "{m}" use a forbidden path : "{p}"'.format(m=mod['name'], p=mod['path']))


def check_app_b64_scripts(updates):
    """
    Trigger a base64 decode on every script given to the API in order to verify their validity
    :param updates: Modules configurations
    """
    if 'modules' in updates:
        for mod in updates['modules']:
            for script in ['build_pack', 'pre_deploy', 'post_deploy', 'after_all_deploy']:
                if script in mod:
                    try:
                        b64decode_utf8(mod[script])
                    except (binascii.Error, UnicodeDecodeError):
                        raise GhostAPIInputError('Error decoding script "{s}" in module: "{m}"'.format(
                            s=script, m=mod["name"]))
    if 'lifecycle_hooks' in updates:
        for script in ['pre_buildimage', 'post_buildimage', 'pre_bootstrap', 'post_bootstrap']:
            if script in updates['lifecycle_hooks']:
                try:
                    b64decode_utf8(updates['lifecycle_hooks'][script])
                except (binascii.Error, UnicodeDecodeError):
                    raise GhostAPIInputError(
                        'Error decoding a script in lifecycle hook: {h}'.format(h=script))
    if 'blue_green' in updates and 'hooks' in updates['blue_green']:
        for script in ['pre_swap', 'post_swap']:
            if script in updates['blue_green']['hooks']:
                try:
                    b64decode_utf8(
                        updates['blue_green']['hooks'][script])
                except (binascii.Error, UnicodeDecodeError):
                    raise GhostAPIInputError('Error decoding a script in blue/green hook: {h}'.format(h=script))


def ghost_api_app_data_input_validator(app):
    check_app_b64_scripts(app)
    check_app_module_path(app)
    check_app_feature_provisioner(app)


def initialize_app_modules(updates, original):
    modules_edited = False
    if 'modules' in updates and 'modules' in original:
        for updated_module in updates['modules']:
            # Set 'initialized' to False by default in case of new modules
            updated_module['initialized'] = False
            updated_module['git_repo'] = updated_module['git_repo'].strip()
            for original_module in original['modules']:
                if updated_module['name'] == original_module['name']:
                    # Restore previous 'initialized' value as 'updated_module' does not contain it (read-only field)
                    updated_module['initialized'] = original_module.get('initialized', False)
                    # Compare all fields except 'initialized'
                    fields = set(original_module.keys() + updated_module.keys())
                    if 'initialized' in fields:
                        fields.remove('initialized')
                    for prop in fields:
                        if field_has_changed(updated_module.get(prop, None),
                                             original_module.get(prop, None)):
                            updated_module['initialized'] = False
                            modules_edited = True
                            # At least one of the module's prop have changed, can exit loop
                            break
                    # Module found, can exit loop
                    break
            else:
                # Module not found in original, so it's a new one
                modules_edited = True
    return updates, modules_edited


def initialize_app_features(updates, original):
    """
    Check for feature modifications
    - feature order
    - attributes modifications

    :param updates:
    :param original:
    :return: bool - if the features changed

    >>> from copy import deepcopy
    >>> initialize_app_features({}, {})
    False

    >>> initialize_app_features({'features': []}, {})
    False

    >>> initialize_app_features({}, {'features': []})
    False

    >>> base_app = {'features': [
    ...     {'name': 'feat1', 'version': 'param=test', 'provisioner': 'salt'},
    ...     {'name': 'feat1', 'version': 'param2=dummy', 'provisioner': 'salt'},
    ...     {'name': 'feat2', 'version': 'other=feat1', 'provisioner': 'ansible'},
    ...     {'name': 'feat2', 'version': 'other=feat2', 'provisioner': 'ansible'},
    ...     {'name': 'feat3', 'version': 'f=f3', 'provisioner': 'ansible'},
    ... ]}
    >>> up_app = deepcopy(base_app)
    >>> initialize_app_features(up_app, base_app)
    False

    >>> up_app = deepcopy(base_app)
    >>> up_app['features'][1]['version'] = 'param=modified'
    >>> initialize_app_features(up_app, base_app)
    True

    >>> up_app = deepcopy(base_app)
    >>> del up_app['features'][4]
    >>> initialize_app_features(up_app, base_app)
    True

    >>> up_app = deepcopy(base_app)
    >>> up_app['features'][2]['version'] = 'other=feat2'
    >>> up_app['features'][3]['version'] = 'other=feat1'
    >>> initialize_app_features(up_app, base_app)
    True
    """
    if 'features' in updates and 'features' in original:
        if not len(updates['features']) == len(original['features']):
            # Different length means that feature have changed
            return True
        for index, updated_feature in enumerate(updates['features']):
            original_feature = original['features'][index]
            if updated_feature['name'] == original_feature['name']:
                # Compare all fields
                fields = set(original_feature.keys() + updated_feature.keys())
                for prop in fields:
                    if field_has_changed(updated_feature.get(prop, None),
                                         original_feature.get(prop, None)):
                        # Feature field is different
                        return True
    return False


def check_field_diff(updates, original, object_name):
    """
    Generic function to check if inner properties of a sub-document has been changed.

    :param updates:
    :param original:
    :param object_name:
    :return: bool - if the object (sub-document) has changed

    >>> from copy import deepcopy
    >>> base_ob = {'a': {
    ...     'x': 1,
    ...     'y': 2,
    ...     'z': 3,
    ... }, 'b': {
    ...     'i': 'a',
    ...     'ii': 'b',
    ... }}
    >>> up_ob = deepcopy(base_ob)
    >>> check_field_diff(up_ob, base_ob, 'a')
    False

    >>> check_field_diff({}, {}, 'a')
    False

    >>> check_field_diff({'a': {}}, {}, 'a')
    False

    >>> check_field_diff({}, {'a': {}}, 'a')
    False

    >>> up_ob = deepcopy(base_ob)
    >>> base_copy_ob = deepcopy(base_ob)
    >>> del base_copy_ob['b']['i']
    >>> check_field_diff(up_ob, base_copy_ob, 'a')
    False

    >>> check_field_diff(up_ob, base_copy_ob, 'b')
    True

    >>> up_ob = deepcopy(base_ob)
    >>> up_ob['a']['y'] = 10
    >>> check_field_diff(up_ob, base_ob, 'a')
    True

    >>> up_ob = deepcopy(base_ob)
    >>> up_ob['a']['y'] = 3
    >>> up_ob['a']['z'] = 2
    >>> check_field_diff(up_ob, base_ob, 'a')
    True

    >>> up_ob = deepcopy(base_ob)
    >>> base_copy_ob = deepcopy(base_ob)
    >>> base_copy_ob['a']['x'] = ""
    >>> del up_ob['a']['x']
    >>> check_field_diff(up_ob, base_copy_ob, 'a')
    False

    >>> up_ob = deepcopy(base_ob)
    >>> base_copy_ob['a']['x'] = ""
    >>> up_ob['a']['x'] = []
    >>> check_field_diff(up_ob, base_copy_ob, 'a')
    True

    >>> up_ob = deepcopy(base_ob)
    >>> base_copy_ob['a']['x'] = 0
    >>> up_ob['a']['x'] = {}
    >>> check_field_diff(up_ob, base_copy_ob, 'a')
    True

    >>> up_ob = deepcopy(base_ob)
    >>> base_copy_ob['a']['x'] = None
    >>> up_ob['a']['x'] = ""
    >>> check_field_diff(up_ob, base_copy_ob, 'a')
    False
    """
    if object_name in updates and object_name in original:
        fields = set(updates[object_name].keys())
        for prop in fields:
            if field_has_changed(updates[object_name].get(prop, None),
                                 original[object_name].get(prop, None)):
                # Field is different
                return True
    return False


def get_pending_changes_objects(data):
    """
    Transform the 'pending_changes' array into a dictionary

    :param data:
    :return: A key (field name) value (original object) dictionary

    >>> base_ob = {'pending_changes': [
    ...     {'field': 'x', 'f1': 1, 'f2': 2},
    ...     {'field': 'y', 'y1': True, 'y2': False},
    ...     {'field': 'z', 'zz': '1', 'zzz': '2'},
    ... ], 'b': {
    ...     'i': 'a',
    ...     'ii': 'b',
    ... }}
    >>> get_pending_changes_objects({})
    {}

    >>> get_pending_changes_objects({'a': 1})
    {}

    >>> get_pending_changes_objects({'pending_changes': []})
    {}

    >>> from pprint import pprint
    >>> res = get_pending_changes_objects(base_ob)
    >>> pprint(sorted(res))
    ['x', 'y', 'z']
    >>> pprint(sorted(res['x']))
    ['f1', 'f2', 'field']
    >>> pprint(sorted(res['y']))
    ['field', 'y1', 'y2']
    >>> pprint(sorted(res['z']))
    ['field', 'zz', 'zzz']
    """
    pending_changes_objects = data.get('pending_changes', [])
    return {ob['field']: ob for ob in pending_changes_objects}


def check_and_set_app_fields_state(user, updates, original, modules_edited=False):
    pending_changes = get_pending_changes_objects(original)

    if modules_edited:
        pending_changes['modules'] = {
            'field': 'modules',
            'user': user,
            'updated': datetime.utcnow(),
        }
    if initialize_app_features(updates, original):
        pending_changes['features'] = {
            'field': 'features',
            'user': user,
            'updated': datetime.utcnow(),
        }

    for object_name in COMMAND_FIELDS:
        if check_field_diff(updates, original, object_name):
            pending_changes[object_name] = {
                'field': object_name,
                'user': user,
                'updated': datetime.utcnow(),
            }

    updates['pending_changes'] = pending_changes.values()
    return updates
