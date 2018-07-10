"""
    Library with all needed data layer access for Ghost objects
"""
# -*- coding: utf-8 -*-

from pymongo import MongoClient
from bson.objectid import ObjectId

from models.apps import APPS_DEFAULT
from settings import MONGO_DBNAME, MONGO_HOST, MONGO_PORT

# DB Access
db = MongoClient(host=MONGO_HOST, port=MONGO_PORT)[MONGO_DBNAME]


def get_fresh_connection():
    return MongoClient(host=MONGO_HOST, port=MONGO_PORT)[MONGO_DBNAME]


def get_deployments_db():
    return db.deploy_histories


# Data Access
def get_app(app_id):
    if not app_id:
        return None
    app = db.apps.find_one({'_id': ObjectId(app_id)})
    normalize_app(app)
    return app


def get_job(job_id):
    if not job_id:
        return None
    job = db.jobs.find_one({'_id': ObjectId(job_id)})
    return job


def get_webhook(webhook_id):
    if not webhook_id:
        return None
    webhook = db.webhooks.find_one({'_id': ObjectId(webhook_id)})
    return webhook


# Data normalization
def normalize_app(app, embed_last_deployment=False):
    """
    eve post-fetch app event hook to normalize special fields, mostly with models breaking changes

    >>> app_logs = {}
    >>> normalize_app(app_logs)
    >>> app_logs.get('log_notifications')
    []

    >>> app_logs = {'log_notifications': [
    ...     'no-reply@fr.clara.net',
    ...     'dummy@fr.clara.net',
    ... ]}
    >>> normalize_app(app_logs)
    >>> [sorted(l.items()) for l in app_logs.get('log_notifications')]
    [[('email', 'no-reply@fr.clara.net'), ('job_states', ['*'])], [('email', 'dummy@fr.clara.net'), ('job_states', ['*'])]]

    >>> app_logs = {'log_notifications': [
    ...     {'email': 'no-reply@fr.clara.net', 'job_states': ['done']},
    ...     'dummy@fr.clara.net',
    ... ]}
    >>> normalize_app(app_logs)
    >>> [sorted(l.items()) for l in app_logs.get('log_notifications')]
    [[('email', 'no-reply@fr.clara.net'), ('job_states', ['done'])], [('email', 'dummy@fr.clara.net'), ('job_states', ['*'])]]

    >>> app_logs = {'log_notifications': [
    ...     {'email': 'no-reply@fr.clara.net'},
    ...     'dummy@fr.clara.net',
    ... ]}
    >>> normalize_app(app_logs)
    >>> [sorted(l.items()) for l in app_logs.get('log_notifications')]
    [[('email', 'no-reply@fr.clara.net'), ('job_states', ['*'])], [('email', 'dummy@fr.clara.net'), ('job_states', ['*'])]]
    """
    if app.get('modules', []):
        dbdeploys = get_deployments_db()
        for module in app.get('modules', []):
            # [GHOST-172] Retrieve each module's last deployment
            query = {
                '$and': [
                    {'app_id': app['_id']},
                    {'module': module['name']}
                ]
            }
            sort = [('timestamp', -1)]
            deployment = dbdeploys.find_one(query, sort=sort)
            if deployment:
                module['last_deployment'] = deployment if embed_last_deployment else deployment['_id']

            # [GHOST-507] Normalize modules.*.source / git_repo
            git_repo = module.get('git_repo')
            module_source = module.get('source', {}) or {}
            module_source['url'] = module_source.get('url', git_repo) or git_repo
            module_source['protocol'] = (module_source.get('protocol', APPS_DEFAULT['modules.source.protocol'])
                                         or APPS_DEFAULT['modules.source.protocol'])
            module_source['mode'] = (module_source.get('mode', APPS_DEFAULT['modules.source.mode'])
                                     or APPS_DEFAULT['modules.source.mode'])
            git_repo = git_repo or module_source['url']

            module['git_repo'] = git_repo
            module['source'] = module_source

    # [GHOST-638] Normalize log_notifications
    log_notifications = []
    for notif in app.get('log_notifications', []):
        if isinstance(notif, basestring):
            log_notifications.append({
                'email': notif,
                'job_states': ['*']
            })
        else:
            if not notif.get('job_states'):
                notif['job_states'] = ['*']
            log_notifications.append(notif)
    app['log_notifications'] = log_notifications


def update_app(app_id, app_data):
    db.apps.update({'_id': app_id}, {'$set': app_data})


def update_job(job_id, job_data):
    db.jobs.update({'_id': job_id}, {'$set': job_data})
