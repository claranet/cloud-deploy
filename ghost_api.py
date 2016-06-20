"""
    Library with all needed functions by Ghost API
"""
# -*- coding: utf-8 -*-
#!/usr/bin/env python

from ghost_tools import ghost_app_object_copy
from eve.methods.post import post_internal
from libs.blue_green import get_blue_green_from_app

OPPOSITE_COLOR = {
    'blue': 'green',
    'green': 'blue'
}

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
    green_app = apps_db.find_one({'$and' : [
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
        update_res = apps_db.update_one({ '_id': app['_id']}, {'$unset': {'blue_green'}})
        if not update_res.matched_count == 1: # if success, 1 row has been updated
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

    if green_app_db[0]['_status'] == 'ERR': # _status == OK when insert done by Eve
        return None

    # Set blue-green params to the Green app
    blue_green = {
        'enable_blue_green': True,
        'color': OPPOSITE_COLOR[color],
        'is_online': False,
        'alter_ego_id': app['_id']
    }

    update_res = apps_db.update_one({ '_id': green_app_db[0]['_id']}, {'$set': { 'blue_green': blue_green }})
    update_res_ami = update_res
    if 'ami' in app: # Keep baked AMI too on green app
        ami_name = app['build_infos']['ami_name']
        update_res_ami = apps_db.update_one({'_id': green_app_db[0]['_id']}, {'$set': {'ami': app['ami'], 'build_infos.ami_name': ami_name}})
    if update_res.matched_count == 1 and update_res_ami.matched_count == 1:
        return green_app_db[0]['_id']
    else:
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
    update_res = apps_db.update_one({ '_id': blue_app['_id']}, {'$set': { 'blue_green': blue_green }})
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
        alter_app = apps_db.find_one({'$and' : [
            {'_id': blue_green.get('alter_ego_id')}
        ]})
        if alter_app:
            # delete_internal('apps', ) -- doesn't exists in Eve for now :(
            return apps_db.delete_one({'_id': blue_green.get('alter_ego_id')}).deleted_count == 1
    return True
