from flask import abort, request
from bson.objectid import ObjectId
from flask_bootstrap import Bootstrap
from redis import Redis
from rq import Queue
from rq_dashboard import RQDashboard
import worker
from eve_docs import eve_docs
from eve import Eve
from auth import BCryptAuth

ghost = Eve(auth=BCryptAuth)
redis_conn_queue = Redis()
queue = Queue(connection=redis_conn_queue, default_timeout=3600)


#FIXME: Implement modules update (reinitialized ?)
def pre_update_app(updates, original):
    if 'modules' in updates:
        for module in updates['modules']:
            module['initialized'] = False


#FIXME: Implement (or not ?) application replacement
def pre_replace_app(item, original):
    pass


#FIXME: implement purge of application (git repo)
def pre_delete_app(item):
    pass


def pre_insert_app(items):
    app = items[0]
    name = app.get('name')
    role = app.get('role')
    env = app.get('env')
    apps = ghost.data.driver.db['apps']
    if apps.find_one({'$and' : [{'name': name}, {'role': role}, {'env': env}]}):
        abort(422)
    for module in app.get('modules'):
        module['initialized'] = False
    app['user'] = request.authorization.username

def pre_insert_job(items):
    job = items[0]
    app_id = job.get('app_id')
    apps = ghost.data.driver.db['apps']
    app = apps.find_one({'_id': ObjectId(app_id)})
    if not app:
        abort(404)
    if job.get('command') == 'deploy':
        for module in job['modules']:
            not_exist = True
            for mod in app['modules']:
                print('app module name is: '+mod['name'])
                if 'name' in module and module['name'] == mod['name']:
                    not_exist = False
            if not_exist:
                abort(422)
    if job['command'] == 'build_image':
        if not ('build_infos' in app.viewkeys()):
            abort(422)
    # FIXME: uncomment the following check when job execution is rock solid
    # jobs = ghost.data.driver.db['jobs']
    # if jobs.find_one({'$and': [{'status': {'$ne': 'done'}}, {'status': {'$ne': 'failed'}}, {'app_id': app_id}]}):
    #     abort(422)
    job['user'] = request.authorization.username
    job['status'] = 'init'
    job['message'] = 'Initializing job'

def post_insert_job(items):
    async_work = worker.Worker()
    job_id = queue.enqueue(async_work.execute, str(items[0]['_id']))

ghost.on_update_apps += pre_update_app
ghost.on_replace_apps += pre_replace_app
ghost.on_delete_apps += pre_delete_app
ghost.on_insert_apps += pre_insert_app
ghost.on_insert_jobs += pre_insert_job
ghost.on_inserted_jobs += post_insert_job

Bootstrap(ghost)
ghost.register_blueprint(eve_docs, url_prefix='/docs')

RQDashboard(ghost)

if __name__ == '__main__':
    ghost.run(host='0.0.0.0')
