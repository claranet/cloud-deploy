"""
    Library with all needed data layer access for Ghost objects
"""
# -*- coding: utf-8 -*-

from pymongo import MongoClient
from bson.objectid import ObjectId

from settings import MONGO_DBNAME, MONGO_HOST, MONGO_PORT, REDIS_HOST


# DB Access
def get_db_connection():
    return MongoClient(host=MONGO_HOST, port=MONGO_PORT)[MONGO_DBNAME]


def get_deployments_db():
    db = get_db_connection()
    return db.deployments


def close_db_connection():
    MongoClient().close()


# Data Access
def get_app(app_id):
    if not app_id:
        return None
    db = get_db_connection()
    app = db.apps.find_one({'_id': ObjectId(app_id)})
    close_db_connection()
    return normalize_app(app)


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
    """
    # Retrieve each module's last deployment
    for module in app.get('modules', []):
        query = {
            '$and': [
                {'app_id': app['_id']},
                {'module': module['name']}
            ]
        }
        sort = [('timestamp', -1)]
        deployment = get_deployments_db().find_one(query, sort=sort)
        if deployment:
            module['last_deployment'] = deployment if embed_last_deployment else deployment['_id']

    # Normalize log_notifications
    log_notifications = []
    for notif in app.get('log_notifications', []):
        if isinstance(notif, basestring):
            log_notifications.append({
                'email': notif,
                'job_states': ['*']
            })
        else:
            log_notifications.append(notif)
    app['log_notifications'] = log_notifications

    return app
