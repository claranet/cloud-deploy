"""
    Library with all needed functions by Ghost API
"""
# -*- coding: utf-8 -*-
# !/usr/bin/env python

import os
import traceback
import binascii
from ghost_tools import ghost_app_object_copy, get_available_provisioners_from_config, b64decode_utf8
from eve.methods.post import post_internal
from libs.blue_green import get_blue_green_from_app

OPPOSITE_COLOR = {
    'blue': 'green',
    'green': 'blue'
}
FORBIDDEN_PATH = ['/', '/tmp', '/var', '/etc', '/ghost', '/root', '/home', '/home/admin']


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
                print('Provisioner "{p}" set for feature "{f}" is not available or not compatible.'.format(
                    p=ft['provisioner'], f=ft['name']))
                return False
    return True


def check_app_module_path(updates):
    """
    Check if all modules path are allowed
    :param updates:
    :return: bool

    >>> check_app_module_path({})
    True

    >>> check_app_module_path({'modules': []})
    True

    >>> check_app_module_path({'modules': [{'name': 'empty'}]})
    False

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/tmp/test'}, {'name': 'mod2', 'path': '/srv/ok'}]}
    >>> check_app_module_path(app)
    True

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/tmp/test/'}, {'name': 'mod2', 'path': '/srv/ok//'}]}
    >>> check_app_module_path(app)
    True

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/tmp/'}, {'name': 'mod2', 'path': '/srv/ok//'}]}
    >>> check_app_module_path(app)
    False

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/'}, {'name': 'mod2', 'path': '/srv/ok//'}]}
    >>> check_app_module_path(app)
    False

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/ghost/x'}, {'name': 'mod2', 'path': '/ghost'}]}
    >>> check_app_module_path(app)
    False

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/ghost/x'}, {'name': 'mod2', 'path': '/ghost////'}]}
    >>> check_app_module_path(app)
    False

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/root/x/..'}, {'name': 'mod2', 'path': '/srv/ok'}]}
    >>> check_app_module_path(app)
    False

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/root/x/.//'}, {'name': 'mod2', 'path': '/srv/ok'}]}
    >>> check_app_module_path(app)
    True

    >>> app = {'_id': 1111, 'env': 'prod', 'name': 'app1', 'role': 'webfront', 'modules': [
    ...     {'name': 'mod1', 'path': '/root/x/.//..//////'}, {'name': 'mod2', 'path': '/srv/ok'}]}
    >>> check_app_module_path(app)
    False
    """
    if 'modules' in updates:
        for mod in updates['modules']:
            if not 'path' in mod:
                return False
            if os.path.abspath(mod['path']) in FORBIDDEN_PATH:
                return False
    return True


def check_app_b64_scripts(updates):
    """
    Trigger a base64 decode on every script given to the API in order to verify their validity
    :param updates:
    :return: bool
    """
    try:
        if 'modules' in updates:
            for mod in updates['modules']:
                for script in ['build_pack', 'pre_deploy', 'post_deploy', 'after_all_deploy']:
                    if script in mod:
                        b64decode_utf8(mod[script])
        if 'lifecycle_hooks' in updates:
            for script in ['pre_buildimage', 'post_buildimage', 'pre_bootstrap', 'post_bootstrap']:
                if script in updates['lifecycle_hooks']:
                    b64decode_utf8(updates['lifecycle_hooks'][script])
        return True
    except binascii.Error:
        traceback.print_exc()
        return False


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
                        if not updated_module.get(prop, None) == original_module.get(prop, None):
                            updated_module['initialized'] = False
                            modules_edited = True
                            # At least one of the module's prop have changed, can exit loop
                            break
                    # Module found, can exit loop
                    break
    return updates, modules_edited


def initialize_app_features(updates, original):
    if 'features' in updates and 'features' in original:
        for updated_feature in updates['features']:
            for original_feature in original['features']:
                if updated_feature['name'] == original_feature['name']:
                    # Compare all fields
                    fields = set(original_feature.keys() + updated_feature.keys())
                    for prop in fields:
                        if not updated_feature.get(prop, None) == original_feature.get(prop, None):
                            # Feature field is different
                            return True
                    break
    return False


def check_field_diff(updates, original, object_name):
    if object_name in updates and object_name in original:
        fields = set(original[object_name].keys() + updates[object_name].keys())
        for prop in fields:
            if not updates[object_name].get(prop, None) == original[object_name].get(prop, None):
                return True

    return False


def check_and_set_app_fields_state(updates, original, modules_edited=False):
    modified_fields = set(original.get('modified_fields', []))

    if modules_edited:
        modified_fields.add('modules')
    if initialize_app_features(updates, original):
        modified_fields.add('features')

    for object_name in ['autoscale', 'blue_green', 'build_infos', 'environment_infos', 'lifecycle_hooks']:
        if check_field_diff(updates, original, object_name):
            modified_fields.add(object_name)

    updates['modified_fields'] = list(modified_fields)
    return updates
