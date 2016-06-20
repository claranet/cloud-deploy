from datetime import datetime

from flask import abort, request
from flask_bootstrap import Bootstrap

from eve import Eve
from eve_docs import eve_docs
from auth import BCryptAuth
from bson.objectid import ObjectId
import json

from redis import Redis
from rq import Queue, cancel_job
import rq_dashboard

from settings import __dict__ as eve_settings
from command import Command
from models.apps import apps
from models.jobs import jobs, CANCELLABLE_JOB_STATUSES, DELETABLE_JOB_STATUSES
from models.deployments import deployments

from ghost_tools import get_rq_name_from_app
from ghost_blueprints import commands_blueprint
from ghost_api import ghost_api_bluegreen_is_enabled, ghost_api_enable_green_app, ghost_api_delete_alter_ego_app, ghost_api_clean_bluegreen_app

def get_apps_db():
    return ghost.data.driver.db[apps['datasource']['source']]

def get_jobs_db():
    return ghost.data.driver.db[jobs['datasource']['source']]

def get_deployments_db():
    return ghost.data.driver.db[deployments['datasource']['source']]

def pre_update_app(updates, original):
    """
    eve pre-update event hook to reset modified modules' 'initialized' field.

    Uninitialized modules stay so, modified or not:

    >>> from copy import deepcopy
    >>> base_original = {'modules': [{'name': 'mod1', 'git_repo': 'git@github.com/test/mod1'}, {'name': 'mod2', 'git_repo': 'git@github.com/test/mod2'}]}
    >>> original = deepcopy(base_original)
    >>> updates = deepcopy(base_original)
    >>> pre_update_app(updates, original)
    >>> updates['modules'][0]['initialized']
    False
    >>> updates['modules'][1]['initialized']
    False

    Initialized modules stay so if not modified:

    >>> original['modules'][0]['initialized'] = True
    >>> original['modules'][1]['initialized'] = True
    >>> updates = deepcopy(base_original)
    >>> pre_update_app(updates, original)
    >>> updates['modules'][0]['initialized']
    True
    >>> updates['modules'][1]['initialized']
    True

    Modified modules get their 'initialized' field reset to False:

    >>> updates = deepcopy(base_original)
    >>> updates['modules'][1]['git_repo'] = 'git@github.com/test/mod2-modified'
    >>> pre_update_app(updates, original)
    >>> updates['modules'][0]['initialized']
    True
    >>> updates['modules'][1]['initialized']
    False

    Modified modules get their 'initialized' field reset to False also in case of new fields:

    >>> updates = deepcopy(base_original)
    >>> updates['modules'][1]['uid'] = '101'
    >>> updates['modules'][1]['gid'] = '102'
    >>> pre_update_app(updates, original)
    >>> updates['modules'][0]['initialized']
    True
    >>> updates['modules'][1]['initialized']
    False

    New modules get their 'initialized' field set to False by default:

    >>> updates = deepcopy(base_original)
    >>> updates['modules'].append({'name': 'mod3', 'git_repo': 'git@github.com/test/mod3'})
    >>> pre_update_app(updates, original)
    >>> updates['modules'][0]['initialized']
    True
    >>> updates['modules'][1]['initialized']
    True
    >>> updates['modules'][2]['initialized']
    False
    """

    # Selectively reset each module's 'initialized' property if any of its other properties have changed
    if 'modules' in updates and 'modules' in original:
        for updated_module in updates['modules']:
            # Set 'initialized' to False by default in case of new modules
            updated_module['initialized'] = False
            for original_module in original['modules']:
                if updated_module['name'] ==  original_module['name']:
                    # Restore previous 'initialized' value as 'updated_module' does not contain it (read-only field)
                    updated_module['initialized'] = original_module.get('initialized', False)
                    # Compare all fields except 'initialized'
                    fields = set(original_module.keys() + updated_module.keys())
                    if 'initialized' in fields:
                        fields.remove('initialized')
                    for prop in fields:
                        if not updated_module.get(prop, None) == original_module.get(prop, None):
                            updated_module['initialized'] = False
                            # At least one of the module's prop have changed, can exit loop
                            break
                    # Module found, can exit loop
                    break

    # Blue/green disabled ?
    try:
        blue_green_section, color = get_blue_green_from_app(updates)
        if blue_green_section and
            'enable_blue_green' in blue_green_section and
            isinstance(blue_green_section['enable_blue_green'], bool) and
            not blue_green_section['enable_blue_green']:

            if not ghost_api_clean_bluegreen_app(get_apps_db(), original):
                abort(422)

            if not ghost_api_delete_alter_ego_app(get_apps_db(), original):
                abort(422)

            del updates['blue_green']
    except Exception as e:
        print e
        abort(500)

def post_update_app(updates, original):
    try:
        # Enable green app only if not already enabled
        blue_green, color = get_blue_green_from_app(original)
        if ghost_api_bluegreen_is_enabled(updates) and not blue_green and not color:
            # Maybe we need to have the "merged" app after update here instead of "original" one ?
            if not ghost_api_enable_green_app(get_apps_db(), original, request.authorization.username):
                abort(422)
    except Exception as e:
        print e
        abort(500)

def pre_replace_app(item, original):
    #TODO: implement (or not?) application replacement
    pass

def pre_delete_app(item):
    #TODO: implement purge of application (git repo clone)
    pass

def post_delete_app(item):
    if not ghost_api_delete_alter_ego_app(get_apps_db(), item):
        abort(422)

def pre_insert_app(items):
    app = items[0]
    name = app.get('name')
    role = app.get('role')
    env = app.get('env')
    blue_green = app.get('blue_green', None)
    # We can now insert a new app with a different color
    if blue_green and blue_green.get('color', None):
        if get_apps_db().find_one({'$and' : [{'name': name}, {'role': role}, {'env': env}, {'blue_green.color': blue_green['color']}]}):
            abort(422)
    else:
        if get_apps_db().find_one({'$and' : [{'name': name}, {'role': role}, {'env': env}]}):
            abort(422)
    for module in app.get('modules'):
        module['initialized'] = False
    app['user'] = request.authorization.username

def post_insert_app(items):
    app = items[0]
    if ghost_api_bluegreen_is_enabled(app):
        if not ghost_api_enable_green_app(get_apps_db(), app, request.authorization.username):
            abort(422)

def post_fetched_app(response):
    # Do we need to embed each module's last_deployment?
    embedded = json.loads(request.args.get('embedded', '{}'))
    embed_last_deployment = embedded.get('modules.last_deployment', False)

    # Retrieve each module's last deployment
    for module in response['modules']:
        query = {
                 '$and': [
                          {'app_id': response['_id']},
                          {'module': module['name']}
                          ]
                 }
        sort = [('timestamp', -1)]
        deployment = get_deployments_db().find_one(query, sort=sort)
        if deployment:
            module['last_deployment'] = deployment if embed_last_deployment else deployment['_id']

def pre_insert_job(items):
    job = items[0]
    app_id = job.get('app_id')
    app = get_apps_db().find_one({'_id': ObjectId(app_id)})
    if not app:
        abort(404)
    if job.get('command') == 'deploy':
        for module in job['modules']:
            not_exist = True
            for mod in app['modules']:
                if 'name' in module and module['name'] == mod['name']:
                    not_exist = False
            if not_exist:
                abort(422)
    if job['command'] == 'build_image':
        if not ('build_infos' in app.viewkeys()):
            abort(422)
    job['user'] = request.authorization.username
    job['status'] = 'init'
    job['message'] = 'Initializing job'

def post_insert_job(items):
    job = items[0]
    job_id = str(job.get('_id'))

    app_id = job.get('app_id')
    app = get_apps_db().find_one({'_id': ObjectId(app_id)})

    # Place job in app's queue 
    rq_job = Queue(name=get_rq_name_from_app(app), connection=ghost.ghost_redis_connection, default_timeout=3600).enqueue(Command().execute, job_id, job_id=job_id)
    assert rq_job.id == job_id

def pre_delete_job(item):
    if item['status'] not in DELETABLE_JOB_STATUSES:
        # Do not allow deleting jobs not in cancelled, done, failed or aborted status
        abort(422)

def pre_delete_job_enqueueings():
    job_id = request.view_args['job_id']
    job = get_jobs_db().find_one({'_id': ObjectId(job_id)})

    if job and job['status'] in CANCELLABLE_JOB_STATUSES:
        # Cancel the job from RQ
        cancel_job(job_id, connection=ghost.ghost_redis_connection)
        get_jobs_db().update({'_id': ObjectId(job_id)}, {'$set': {'status': 'cancelled', 'message': 'Job cancelled', '_updated': datetime.now()}})
        return

    # Do not allow cancelling jobs not in init status
    abort(422)

# Create ghost app, explicitly specifying the settings to avoid errors during doctest execution
ghost = Eve(auth=BCryptAuth, settings=eve_settings)
Bootstrap(ghost)
ghost.config.from_object(rq_dashboard.default_settings)
ghost.register_blueprint(rq_dashboard.blueprint, url_prefix='/rq')
ghost.register_blueprint(eve_docs, url_prefix='/docs/api')

# Register eve hooks
ghost.on_fetched_item_apps += post_fetched_app
ghost.on_update_apps += pre_update_app
ghost.on_updated_apps += post_update_app
ghost.on_replace_apps += pre_replace_app
ghost.on_delete_item_apps += pre_delete_app
ghost.on_deleted_item_apps += post_delete_app
ghost.on_insert_apps += pre_insert_app
ghost.on_inserted_apps += post_insert_app
ghost.on_insert_jobs += pre_insert_job
ghost.on_inserted_jobs += post_insert_job
ghost.on_delete_item_jobs += pre_delete_job
ghost.on_delete_resource_job_enqueueings += pre_delete_job_enqueueings


ghost.ghost_redis_connection = Redis()

# Register non-mongodb resources as plain Flask blueprints (they won't appear in /docs)
ghost.register_blueprint(commands_blueprint)

if __name__ == '__main__':
    ghost.run(host='0.0.0.0', debug=True)
