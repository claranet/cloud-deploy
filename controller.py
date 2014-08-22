# -*- coding: utf-8 -*-
#!/usr/bin/env python

from flask import Flask, request, jsonify, render_template
# from flask.ext.mail import Message, Mail
from rq.job import Job
from rq import Queue
from rq_dashboard import RQDashboard
# from task import queue, redis_conn_queue
import logging
import worker
import os
from redis import Redis
from pymongo import MongoClient
import logging
import sys

root = logging.getLogger()
root.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)

redis_conn_queue = Redis()
queue = Queue(connection=redis_conn_queue)

app = Flask(__name__)
# mail = Mail()
RQDashboard(app)
client = MongoClient()
db = client.ghost

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register_app():
    """
    Register a new app in the Continuous Deployment Ghost system
    input: JSON formated data
    app: name of the application (ie: worldbestbars)
    role: role of the instances (ie: webserver)
    env: environment (ie: staging, prod)
    name: (optional)
    git_repo: git repository URL
    git_login: git user
    git_pass: git password
    key_path: Path of the SSH key used to deploy new app (TODO: replace by Salt)
    bucket_s3: Bucket used to store package files
    aws_region: Region used for deployement
    output: Status of the request
    """
    try:
        data = request.get_json(force=True)
        check_mandatory = ['app', 'role', 'env', 'git_repo', 'git_login',
                'git_password', 'key_path', 'bucket_s3', 'aws_region', 'notif_arn']
        for key in check_mandatory:
            try:
                data[key]
            except KeyError, e:
                return jsonify({'status': 400, 'message': 'Malformed request, check key attributes: %s' % e}), 400
        app_exist = db.apps.find_one({'$and' : [ {'app': data['app']}, {'role': data['role']}, {'env': data['env']}]})
        if (app_exist):
            return jsonify({'status': 400, 'message': 'App configuration already exist'}), 400
        new_app = \
                {
                        'app': data['app'],
                        'role': data['role'],
                        'env': data['env'],
                        'git_repo': data['git_repo'],
                        'git_login': data['git_login'],
                        'git_password': data['git_password'],
                        'bucket_s3': data['bucket_s3'],
                        'aws_region': data['aws_region'],
                        'log_notifications': data['log_notifications'],
                        'key_path': data['key_path'],
                        'notif_arn': data['notif_arn']
                }
        db.apps.insert(new_app)
    except Exception, e:
        return jsonify({'status': 400, 'message': e.message}), 400
    return jsonify({'status': 200, 'message': 'Registered'}), 200

@app.route('/deploy', methods=['POST'])
def deploy_app():
    """
    Deploy app
    """
    data = request.get_json(force=True)
    check_mandatory = ['app', 'role', 'env']
    for key in check_mandatory:
        try:
            data[key]
        except KeyError, e:
            return jsonify({'status': 400, 'message': 'Malformed request, check key attributes: %s' % e}), 400
    if 'branch' in data.keys():
        commit = data['branch']
    elif 'commit' in data.keys():
        commit = data['commit']
    app_exist = db.apps.find_one({'$and' : [ {'app': data['app']}, {'role': data['role']}, {'env': data['env']}]})
    if not app_exist:
        return jsonify({'status': 400, 'message': 'Application is not registered in the system, contact Morea'}), 400
    task_exist = db.tasks.find_one({ '$and' : [{ 'status' : 'in_progress'}, {'app_id': app_exist['_id']} ] })
    if task_exist:
        return jsonify({'status': 400, 'message': 'Task already exist wait for it to complete', 'job_id': '%s' % task_exist['job_id']}), 400
    async_work = worker.Worker(app_exist, dry_run=True)
    job = queue.enqueue(async_work.deploy_app, commit=commit)
    return jsonify({'status': 200, 'message': 'Job launched', 'job_id': job.id})


@app.route('/deploy/log', methods=['GET'])
def get_deploy_log():
    """
    Retrieve log 
    """
    pass


@app.route('/configure', methods=['POST'])
def configure():
    data = request.get_json(force=True)
    check_mandatory = ['aws_key', 'aws_secret']


if __name__ == '__main__':
    app.run(debug=True)
