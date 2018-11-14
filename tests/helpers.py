import collections
import flask
import os
import sys
from glob import glob
import datetime

import simplejson
from mock import Mock

from ghost_tools import b64encode_utf8

LOG_FILE = 'log_file'


def void(*args, **kwargs):
    pass


def _dict_update_recursive(d, u):
    py2 = sys.version_info[0] < 3
    iter_func = u.items if py2 else u.iteritems
    for k, v in iter_func():
        if isinstance(v, collections.Mapping):
            r = _dict_update_recursive(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


def get_test_application(**kwargs):
    """
    Factory that creates ghost applications. Any propertiy can be overrided with kwargs
    """
    return _dict_update_recursive({
        "ami": "ami-abcdef",
        "autoscale": {
            "enable_metrics": False,
            "max": 2,
            "min": 2,
            "name": "as.test"
        },
        "blue_green": {
            "enable_blue_green": False
        },
        "build_infos": {
            "source_ami": "ami-source",
            "ssh_username": "admin",
            "subnet_id": "subnet-test",
            "source_container_image": "lxd-container-image-test"
        },
        "env": "test",
        "env_vars": [
            {
                "var_key": "EMPTY_ENV"
            }
        ],
        "environment_infos": {
            "instance_profile": "iam.profile.test",
            "public_ip_address": False,
            "instance_tags": [
                {
                    "tag_name": "Name",
                    "tag_value": "ec2.name.test"
                },
                {
                    "tag_name": "tag-name",
                    "tag_value": "tag-value"
                }
            ],
            "key_name": "key-test",
            "security_groups": [
                "sg-test"
            ],
            "subnet_ids": [
                "subnet-test"
            ],
            "optional_volumes": []
        },
        "features": [
            {
                "name": "feature-name",
                "version": "feature-version"
            },
            {
                "name": "feature-ansible",
                "version": "feature-property=property",
                "provisioner": "ansible"
            }            
        ],
        "instance_type": "t2.medium",
        "lifecycle_hooks": {
            "post_bootstrap": "",
            "post_buildimage": "",
            "pre_bootstrap": "",
            "pre_buildimage": ""
        },
        "log_notifications": [
            "test-notif@fr.clara.net"
        ],
        "modules": [
            {
                "gid": 33,
                "git_repo": "git@github.com:claranet/cloud-deploy.dummy.git",
                "name": "dummy",
                "path": "/var/www/dummy",
                "scope": "code",
                "uid": 33
            }
        ],
        "name": "test-app",
        "region": "eu-west-1",
        "role": "webfront",
        "safe-deployment": {
            "load_balancer_type": "elb",
            "wait_after_deploy": 10,
            "wait_before_deploy": 10
        },
        "user": "claranet",
        "vpc_id": "vpc-test"
    }, kwargs)


def get_test_config(**kwargs):
    """
    Factory that creates ghost configuration. Any propertiy can be overrided with kwargs
    """
    return _dict_update_recursive({
            'bucket_s3': 's3.cloud-deploy-packages',
            'blue_green': {
                'purgebluegreen': {'destroy_temporary_elb': True},
                'preparebluegreen': {'copy_ami': False, 'module_deploy_required': False},
                'enabled': True,
                'swapbluegreen': {
                    'healthcheck_timeout': 2,
                    'healthcheck_interval': 5,
                    'registreation_timeout': 60,
                    'healthcheck_healthy_threshold': 2}},
            'bucket_region': 'eu-central-1',
            'use_ssh_config': True,
            'mongo_host': 'backend',
            'ghost_base_url': 'http://localhost',
            'ghost_root_path': os.path.dirname(os.path.dirname(__file__)),
            'container': {
                'debug': True,
                'endpoint': 'http://lxd-image-endpoint:1234',
                'client_endpoint': 'http://lxd-client-endpoint:5678'
            },
            'display_amis_from_aws_accounts': ['123456789012', '987654321098'],
            'redis_host': 'queue',
            'slack_configs': [{
                'message_prefix': 'Ghost job triggered',
                 'webhooks_endpoint': 'https://hooks.slack.com/services/XX_KEY_XX',
                 'channel': '#ghost-deployments',
                 'bot_name': 'Claranet Cloud Deploy'
            }],
            'key_path': '/usr/local/share/ghost/.ssh/my_key.pem',
            'deployment_package_retention': {'prod': 42, 'dev': 3},
            'features_provisioners': {
                'salt': {'git_revision': 'master', 'git_repo': 'git@github.com:claranet/salt-formulas.git'}},
            'api_base_url': 'http://api:5000',
            'ses_settings': {
                'aws_secret_key': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'mail_from': 'no-reply@cloud-deploy.io',
                'aws_access_key': 'AKIAIOSFODNN7EXAMPLE',
                'region': 'eu-west-1'
            }
        },
        kwargs)


def mocked_logger(msg, file):
    print(msg)


class DictObject(object):
    def __init__(self, **d):
        self.__dict__.update(d)


def get_aws_data(data_name, as_object=False):
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'aws_data', '{}.json'.format(data_name))
    if not os.path.isfile(filename):
        raise ValueError("File not found {}".format(filename))
    with open(filename, 'r') as f:
        d = simplejson.load(f)
        if as_object:
            if d.__iter__:
                return [DictObject(**e) for e in d]
            return DictObject(**d)
        return d


def get_aws_data_paginator(data_name, as_object=False):
    files = sorted(glob("{}/{}-page[0-9].json".format(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), 'aws_data'),
        data_name
    )))

    def paginate():
        for f in files:
            yield get_aws_data(os.path.splitext(f)[0], as_object=as_object)
    paginator = Mock()
    paginator.paginate = paginate
    return paginator


def get_dummy_bash_script(b64_encoding=False):
    script = """#!/bin/bash
set -x
echo "Dummy"
"""
    return b64encode_utf8(script) if b64_encoding else script


def create_test_app_context():
    app = flask.Flask(__name__)
    app.config.update(REQUEST_METHOD='GET', SERVER_NAME='localhost', SERVER_PORT='5000', SECRET_KEY='a random string',
                      WTF_CSRF_SECRET_KEY='a random string')
    app.config['wsgi.url_scheme'] = 'http'
    app.config['PUBLIC_METHODS'] = []
    app.config['ALLOWED_ROLES'] = []
    app.config['ALLOWED_READ_ROLES'] = []
    app.auth = {}
    app.app_context().push()
    request_context = app.request_context(app.config)
    request_context.request.environ['wsgi.errors'] = None
    request_context.push()


def mock_job_post():
    return {
        '_updated': datetime.datetime.now(),
        '_latest_version': 1,
        '_version': 1,
        '_links': {
            'self': {
                'href': u'my/test/test',
                'title': 'job'
            }
        },
        '_created': datetime.datetime.now(),
        '_status': 'OK',
        '_id': '5b1e82bae617250001845a81',
        '_etag': '1c501c0ffcd8212de99e44e1971d6568f19ffb40'
    }, '', '', 200, ''
