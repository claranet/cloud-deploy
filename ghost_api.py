from ghost_tools import ghost_app_object_copy
from eve.methods.post import post_internal

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
    blue_green = app.get('blue_green')
    color = blue_green.get('color', 'blue') if blue_green else 'blue'
    green_app = apps_db.find_one({'$and' : [
        {'name': name},
        {'role': role},
        {'env': env},
        {'blue_green.color': OPPOSITE_COLOR[color]}
    ]})
    return green_app

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

    # Set blue-green params to the Green app
    blue_green = {
        'enable_blue_green': True,
        'color': OPPOSITE_COLOR[color],
        'is_online': False,
        'alter_ego_id': app['_id']
    }

    update_res = apps_db.update_one({ '_id': green_app_db[0]['_id']}, {'$set': { 'blue_green': blue_green }})
    print update_res
    if update_res.matched_count == 1:
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
