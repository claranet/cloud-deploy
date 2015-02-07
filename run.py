from flask import abort
from bson.objectid import ObjectId
from flask.ext.bootstrap import Bootstrap
from redis import Redis
from rq import Queue
from rq_dashboard import RQDashboard
import worker
from eve_docs import eve_docs
from eve import Eve



def pre_insert_app(items):
    print 'begin'
    name = items[0].get('name')
    role = items[0].get('role')
    role = 'test'
    env = items[0].get('env')
    apps = ghost.data.driver.db['apps']
    app = apps.find_one({'$and' : [{'name': name}, {'role': role}, {'env': env}]})
    if app:
        abort(422)

def pre_insert_job(items):
    app_id = items[0].get('app_id')
    apps = ghost.data.driver.db['apps']
    jobs = ghost.data.driver.db['jobs']
    app = apps.find_one({'_id': ObjectId(app_id)})
    if not app:
        abort(404)
    job = jobs.find_one({'$and': [{'status': {'$ne': 'done'}},
                                  {'status': {'$ne': 'failed'}},
                                  {'app_id': app_id}]})
    # FIXME: comment need to be removed
    #if job:
    #    abort(422)
    items[0]['status'] = 'init'

def post_insert_job(items):
    async_work = worker.Worker()
    job_id = queue.enqueue(async_work.execute, str(items[0]['_id']))

ghost = Eve()
redis_conn_queue = Redis()
queue = Queue(connection=redis_conn_queue, default_timeout=0)

ghost.on_insert_apps += pre_insert_app
ghost.on_insert_jobs += pre_insert_job
ghost.on_inserted_jobs += post_insert_job

Bootstrap(ghost)
ghost.register_blueprint(eve_docs, url_prefix='/docs')

RQDashboard(ghost)

if __name__ == '__main__':
    ghost.run(debug=True)
