from flask import abort, request
from flask_bootstrap import Bootstrap

from eve import Eve
from eve_docs import eve_docs
from auth import BCryptAuth
from bson.objectid import ObjectId

from redis import Redis
from rq import Queue
from rq_dashboard import RQDashboard

from settings import __dict__ as eve_settings
from command import Command


def get_apps_db():
    return ghost.data.driver.db['apps']

def get_rq_name_from_app(app):
    """
    Returns an RQ queue name for a given ghost app

    >>> get_rq_name_from_app({'env': 'prod', 'name': 'App1', 'role': 'webfront'})
    'prod:App1:webfront'
    """
    return '{env}:{name}:{role}'.format(env=app['env'], name=app['name'], role=app['role'])

def pre_update_app(updates, original):
    #TODO: implement selective modules update instead of reinitializing all modules
    if 'modules' in updates:
        for module in updates['modules']:
            module['initialized'] = False

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
    rq_job = Queue(get_rq_name_from_app(app), ghost.ghost_redis_connection).enqueue(Command().execute, job_id, job_id=job_id)
    assert rq_job.id == job_id


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


ghost.ghost_redis_connection = Redis()


if __name__ == '__main__':
    ghost.run(host='0.0.0.0')
