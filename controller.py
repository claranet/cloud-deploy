# -*- coding: utf-8 -*-
#!/usr/bin/env python

from flask import Flask, request, jsonify, render_template
from flask_sockets import Sockets
# from flask.ext.mail import Message, Mail
from rq.job import Job
# from task import queue, redis_conn_queue
import logging
from task import task_deploy
import os
from models import db, CDApp


app = Flask(__name__)
app.debug = True
sockets = Sockets(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ghost.db'
logger = logging.getLogger(__name__)
# mail = Mail()
db.init_app(app)

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
    git_user: git user
    git_pass: git password
    key_path: Path of the SSH key used to deploy new app (TODO: replace by Salt)
    output: Status of the request
    """
    try:
        data = request.get_json(force=True)
        check_mandatory = ['app', 'role', 'env', 'git_repo', 'git_user',
                'git_password', 'key_path']
        for key in check_mandatory:
            try:
                data[key]
            except KeyError, e:
                return jsonify({'status': 400, 'message': 'Malformed request, check key attributes: %s' % e}), 400
        app_exist = CDApp.query.filter_by(app=data['app'], role=data['role'], env=data['env']).first()
        if (app_exist):
            return jsonify({'status': 400, 'message': 'App configuration already exist'}), 400
        new_app = CDApp(data['app'], data['role'], data['env'], data['git_repo'],
        data['git_user'], data['git_password'], data['key_path'])
        db.session.add(new_app)
        db.session.commit()
    except Exception, e:
        return jsonify({'status': 400, 'message': e}), 400
    return jsonify({'status': 200, 'message': 'Registered'}), 200

@app.route('/deploy', methods=['POST'])
def deploy_app():
    """
    Deploy app
    """
    data = request.get_json(force=True)
    check_mandatory_fields = ['app', 'role', 'env']
    for key in check_mandatory:
        try:
            data[key]
        except KeyError, e:
            return jsonify({'status': 400, 'message': 'Malformed request, check key attributes: %s' % e}), 400
    if 'branch' in data.keys():
        data['branch']
    elif 'commit' in data.keys():
        data['commit']
    app_exist = CDApp.query.filter_by(app=data['app'], role=data['role'], env=data['env']).first()
    if not app_exist:
        return jsonify({'status': 400, 'message': 'Application is not registered in the system, contact Morea'}), 400
    task_exist = Task.query.filter(app_id == app_exist.id, status != 'done', status != 'failed')
    if task_exist:
        return jsonify({'status': 400, 'message': 'Task already exist wait for it to complete', 'job_id': '%s' % task_exist.job_id}), 400
    job = queue.enqueue(task_deploy)
    task = Task(app_exist.id, job.id, 'in progress')
    session.db.add(task)
    session.db.commit()
    return jsonify({'status': 200, 'message': 'Job launched', 'job_id': job.id})


@app.route('/deploy/log', methods=['GET'])
def get_deploy_log():
    """
    Retrieve log 
    """
    pass


@sockets.route('/echo')
def echo_socket(ws):
    while ws.socket is not None:
        message = ws.receive()
        ws.send("HelloWorld")
        gevent.sleep(5)

if __name__ == '__main__':
    app.run()
