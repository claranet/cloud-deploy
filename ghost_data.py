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


def close_db_connection():
    MongoClient().close()


# Data Access
def get_app(app_id):
    if not app_id:
        return None
    db = get_db_connection()
    app = db.apps.find_one({'_id': ObjectId(app_id)})
    close_db_connection()
    return app


def get_job(job_id):
    if not job_id:
        return None
    db = get_db_connection()
    job = db.jobs.find_one({'_id': ObjectId(job_id)})
    close_db_connection()
    return job