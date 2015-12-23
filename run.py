from datetime import datetime

from flask import abort, request
from flask_bootstrap import Bootstrap

from eve import Eve
from eve_docs import eve_docs
from auth import BCryptAuth
from bson.objectid import ObjectId

from redis import Redis
from rq import Queue, cancel_job
from rq_dashboard import RQDashboard

from settings import __dict__ as eve_settings
from command import Command
from models.jobs import CANCELLABLE_JOB_STATUSES, DELETABLE_JOB_STATUSES

def get_apps_db():
    return ghost.data.driver.db['apps']

def get_jobs_db():
    return ghost.data.driver.db['jobs']

def get_rq_name_from_app(app):
    """
    Returns an RQ queue name for a given ghost app

    >>> get_rq_name_from_app({'env': 'prod', 'name': 'App1', 'role': 'webfront'})
    'prod:App1:webfront'
    """
    return '{env}:{name}:{role}'.format(env=app['env'], name=app['name'], role=app['role'])

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
    """

    # Selectively reset each module's 'initialized' property if any of its other properties have changed
    if 'modules' in updates and 'modules' in original:
        for updated_module in updates['modules']:
            for original_module in original['modules']:
                if updated_module['name'] ==  original_module['name']:
                    # Restore previous 'initialized' value as 'updated_module' does not contain it (read-only field)
                    updated_module['initialized'] = original_module.get('initialized', False)
                    for prop in ['git_repo', 'scope', 'build_pack', 'pre_deploy', 'post_deploy', 'path']:
                        if not updated_module.get(prop, None) == original_module.get(prop, None):
                            updated_module['initialized'] = False
                            # At least on the module's prop have changed, can exit loop
                            break
                    # Module found, can exit loop
                    break

def pre_replace_app(item, original):
    #TODO: implement (or not?) application replacement
    pass

def pre_delete_app(item):
    #TODO: implement purge of application (git repo clone)
    pass

def post_delete_app(item):
    pass

def pre_insert_app(items):
    app = items[0]
    name = app.get('name')
    role = app.get('role')
    env = app.get('env')
    if get_apps_db().find_one({'$and' : [{'name': name}, {'role': role}, {'env': env}]}):
        abort(422)
    for module in app.get('modules'):
        module['initialized'] = False
    app['user'] = request.authorization.username

def post_insert_app(items):
    pass

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
RQDashboard(ghost)
ghost.register_blueprint(eve_docs, url_prefix='/docs')

# Register eve hooks
ghost.on_update_apps += pre_update_app
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


if __name__ == '__main__':
    ghost.run(host='0.0.0.0')
