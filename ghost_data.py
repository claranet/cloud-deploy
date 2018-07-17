"""
    Library with all needed data layer access for Ghost objects
"""
# -*- coding: utf-8 -*-

from pymongo import MongoClient
from bson.objectid import ObjectId

from models.apps import apps_default
from settings import MONGO_DBNAME, MONGO_HOST, MONGO_PORT, REDIS_HOST


# DB Access
def get_db_connection():
    return MongoClient(host=MONGO_HOST, port=MONGO_PORT)[MONGO_DBNAME]


def get_deployments_db():
    db = get_db_connection()
    return db.deploy_histories


def close_db_connection():
    MongoClient().close()


# Data Access
def get_app(app_id):
    if not app_id:
        return None
    db = get_db_connection()
    app = db.apps.find_one({'_id': ObjectId(app_id)})
    close_db_connection()
    normalize_app(app)
    return app


def get_job(job_id):
    if not job_id:
        return None
    db = get_db_connection()
    job = db.jobs.find_one({'_id': ObjectId(job_id)})
    close_db_connection()
    return job


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
        db = get_deployments_db()
        for module in app.get('modules', []):
            # [GHOST-172] Retrieve each module's last deployment
            query = {
                '$and': [
                    {'app_id': app['_id']},
                    {'module': module['name']}
                ]
            }
            sort = [('timestamp', -1)]
            deployment = db.find_one(query, sort=sort)
            if deployment:
                module['last_deployment'] = deployment if embed_last_deployment else deployment['_id']

            # [GHOST-507] Normalize modules.*.source / git_repo
            git_repo = module.get('git_repo')
            module_source = module.get('source', {}) or {}
            module_source['url'] = module_source.get('url', git_repo) or git_repo
            module_source['protocol'] = (module_source.get('protocol', apps_default['modules.source.protocol'])
                                            or apps_default['modules.source.protocol'])
            module_source['mode'] = (module_source.get('mode', apps_default['modules.source.mode'])
                                        or apps_default['modules.source.mode'])
            git_repo = git_repo or module_source['url']

            module['git_repo'] = git_repo
            module['source'] = module_source

        close_db_connection()

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
