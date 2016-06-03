"""Library pertaining to blue/green commands."""


def get_blue_green_apps(app, apps_db):
    """
    Return app and alter_ego_app if at least one is online.

    Online app is returned first.
    """
    if app.get('blue_green') and app['blue_green'].get('alter_ego_id'):
        alter_ego_app = apps_db.find_one(
            {'_id': app['blue_green']['alter_ego_id']}
        )
        if app['blue_green']['is_online']:
            return app, alter_ego_app
        else:
            if alter_ego_app['blue_green']['is_online']:
                return alter_ego_app, app
            else:
                return None, None
    else:
        return None, None
