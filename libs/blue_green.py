"""Library pertaining to blue/green commands."""
# -*- coding: utf-8 -*-
#!/usr/bin/env python

import sys
from ghost_log import log
from .deploy import get_path_from_app_with_color
from settings import cloud_connections, DEFAULT_PROVIDER

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

def check_app_manifest(app, config, log_file):
    key_path = get_path_from_app_with_color(app) + '/MANIFEST'
    cloud_connection = cloud_connections.get(app.get('provider', DEFAULT_PROVIDER))(log_file)
    conn = cloud_connection.get_connection(config.get('bucket_region', app['region']), ["s3"])
    bucket = conn.get_bucket(config['bucket_s3'])
    key = bucket.get_key(key_path)
    if not key:
        return False
    manifest = key.get_contents_as_string()
    if sys.version > '3':
        manifest = manifest.decode('utf-8')
    nb_deployed_modules = len(manifest.strip().split('\n'))
    nb_app_modules = len(app['modules'])
    return nb_deployed_modules == nb_app_modules
