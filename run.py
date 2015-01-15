from flask import abort
from bson.objectid import ObjectId
from flask.ext.bootstrap import Bootstrap
from eve_docs import eve_docs
from eve import Eve


ghost = Eve()

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
    if job:
        abort(422)
    items[0]['status'] = 'init'
    # TODO:
    #worker.queue()


ghost.on_insert_jobs += pre_insert_job

Bootstrap(ghost)
ghost.register_blueprint(eve_docs, url_prefix='/docs')



if __name__ == '__main__':
    ghost.run(host='0.0.0.0')
