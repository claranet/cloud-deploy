# -*- coding: utf-8 -*-
#!/usr/bin/env python

from flask.ext.sqlalchemy import SQLAlchemy
from werkzeug import generate_password_hash, check_password_hash
import datetime

db = SQLAlchemy()

class CDApp(db.Model):
    """
    Continous Deployment supported App
    """
    __tablename__ = 'apps'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    app = db.Column(db.String(50))
    role = db.Column(db.String(50))
    env = db.Column(db.String(50))
    git_path = db.Column(db.String(256))
    git_login = db.Column(db.String(50))
    git_password = db.Column(db.String(50))
    key_path = db.Column(db.String(256))
    bucket_s3 = db.Column(db.String(256))
    aws_region = db.Column(db.String(50))
    tasks = db.relationship("Task", backref="app")

    def __init__(self, app, role, env, git_path, git_login, git_password, key_path, bucket_s3, aws_region, name=""):
        self.name = name
        self.app = app
        self.role = role
        self.env = env
        self.git_path = git_path
        self.git_login = git_login
        self.git_password = git_password
        self.key_path = key_path
        self.bucket_s3 = bucket_s3
        self.aws_region = aws_region

    def __str__(self):
        return "<id: %s, app: %s, name: %s, role: %s, env: %s>" % (self.id, self.app, self.name, self.role, self.env)


class Configuration(db.Model):
    __tablename__ = 'configuration'
    id = db.Column(db.Integer, primary_key=True)
    aws_key = db.Column(db.String(200))
    aws_secret = db.Column(db.String(200))

    def __init__(self, aws_key, aws_secret):
        self.aws_key = aws_key
        self.aws_secret = aws_secret


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100))
    app_id = db.Column(db.Integer, db.ForeignKey('apps.id'))
    created_at = db.Column(db.DateTime)
    job = db.Column(db.String(200))
    #status = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(100))

    def __init__(self, app_id, action, job, status):
        self.app_id = app_id
        self.action = action
        self.job = job
        self.created_at = datetime.datetime.now()
        self.status = status


if __name__ == "__main__":
    from flask import Flask
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ghost.db'
    db.init_app(app)
    with app.app_context():
        db.metadata.create_all(db.engine)
        db.session.commit()
        tas = Task.query.filter("app_id=:app_id AND status != 'done' AND status != 'failed'").params(app_id=1).first()
        print(tas.job)
