from settings import cloud_connections, DEFAULT_PROVIDER

def get_path_from_app(app):
    """
    >>> get_path_from_app({'name': 'AppName', 'env': 'prod', 'role': 'webfront'})
    '/ghost/AppName/prod/webfront'
    """
    return "/ghost/{name}/{env}/{role}".format(name=app['name'], env=app['env'], role=app['role'])

def get_path_from_app_with_color(app):
    """
    >>> get_path_from_app({'name': 'AppName', 'env': 'prod', 'role': 'webfront', 'blue_green': {'color': 'blue'}})
    '/ghost/AppName/prod/webfront/blue'
    """
    if 'blue_green' in app and 'color' in app['blue_green']:
        return "/ghost/{name}/{env}/{role}/{color}".format(name=app['name'], env=app['env'],
                                                           role=app['role'], color=app['blue_green']['color'])
    else:
        return get_path_from_app(app)

def update_app_manifest(app, config, module, package, log_file):
    """
    Update the app manifest into S3
    """
    key_path = get_path_from_app_with_color(app) + '/MANIFEST'
    cloud_connection = cloud_connections.get(app.get('provider', DEFAULT_PROVIDER))(log_file)
    conn = cloud_connection.get_connection(config.get('bucket_region', app['region']), ["s3"])
    bucket = conn.get_bucket(config['bucket_s3'])
    key = bucket.get_key(key_path)
    modules = []
    module_exist = False
    all_app_modules_list = get_app_module_name_list(app['modules'])
    data = ""
    if not key: # if the 'colored' MANIFEST doesn't' exist, maybe the legacy one exists and we should clone it
        legacy_key_path = get_path_from_app(app) + '/MANIFEST'
        legacy_key = bucket.get_key(key_path)
        if legacy_key:
            key = legacy_key.copy(bucket, key_path)
    if key:
        manifest = key.get_contents_as_string()
        if sys.version > '3':
            manifest = manifest.decode('utf-8')
        for line in manifest.split('\n'):
            if line:
                mod = {}
                tmp = line.split(':')
                mod['name'] = tmp[0]
                if mod['name'] == module['name']:
                    mod['package'] = package
                    mod['path'] = module['path']
                    module_exist = True
                else:
                    mod['package'] = tmp[1]
                    mod['path'] = tmp[2]
                # Only keep modules that have not been removed from the app
                if mod['name'] in all_app_modules_list:
                    mod['index'] = all_app_modules_list.index(mod['name'])
                    modules.append(mod)
    if not key:
        key = bucket.new_key(key_path)
    if not module_exist:
        modules.append({
            'name': module['name'],
            'package': package,
            'path': module['path'],
            'index': all_app_modules_list.index(module['name'])
        })
    for mod in sorted(modules, key=lambda mod: mod['index']):
        data = data + mod['name'] + ':' + mod['package'] + ':' + mod['path'] + '\n'

        key.set_contents_from_string(data)
        key.close()
