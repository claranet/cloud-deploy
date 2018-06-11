from flask import Flask, json
from mock import patch
from werkzeug.exceptions import HTTPException

from ghost_blueprints import handle_webhook
from helpers import mock_job_post
from helpers_webhook import load_bitbucket_conf, load_github_conf, load_gitlab_conf


@patch('webhooks.webhook_handler.post_internal')
@patch('webhooks.parsers.base.get_app')
@patch('webhooks.webhook_handler.get_webhook')
def test_webhook_github(get_webhook, get_app, post_internal):
    app = Flask(__name__)

    # Overwrite DB related function's behavior
    def load_mocks(conf):
        get_app.return_value = conf['app']
        get_webhook.return_value = conf['webhook']
        post_internal.return_value = mock_job_post()

    # Positive tests
    test_name = 'test_github_push'
    conf = load_github_conf()
    load_mocks(conf)
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        handle_webhook(test_name)

    test_name = 'test_github_merge'
    conf = load_github_conf('merge')
    load_mocks(conf)
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        handle_webhook(test_name)

    test_name = 'test_github_tag'
    conf = load_github_conf('tag')
    load_mocks(conf)
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        handle_webhook(test_name)

    # Negative tests
    load_github_conf()
    test_name = 'test_github_invalid_rev'
    conf['webhook']['rev'] = 'test'
    load_mocks(conf)
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        try:
            handle_webhook(test_name)
        except HTTPException as e:
            assert e.code == 403
            assert e.description == ('webhook request doesn\'t match its Cloud Deploy configuration: test_'
                                     'github_invalid_rev. error: invalid revision.')

    test_name = 'test_github_invalid_payload'
    conf = load_github_conf()
    del conf['payload']['repository']
    conf['payload_json'] = json.dumps(conf['payload'])
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        try:
            handle_webhook(test_name)
        except HTTPException as e:
            assert e.code == 422
            assert e.description == 'invalid webhook request payload: \'repository\''


@patch('webhooks.webhook_handler.post_internal')
@patch('webhooks.parsers.base.get_app')
@patch('webhooks.webhook_handler.get_webhook')
def test_webhook_bitbucket(get_webhook, get_app, post_internal):
    conf = load_bitbucket_conf()
    app = Flask(__name__)

    # Overwrite DB related function's behavior
    def load_mocks(conf):
        get_app.return_value = conf['app']
        get_webhook.return_value = conf['webhook']
        post_internal.return_value = mock_job_post()

    # Positive tests
    load_mocks(conf)
    test_name = 'test_bitbucket_simple'
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        handle_webhook(test_name)

    test_name = 'test_bitbucket_merge'
    conf = load_bitbucket_conf('merge')
    load_mocks(conf)
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        handle_webhook(test_name)

    test_name = 'test_bitbucket_tag'
    conf = load_bitbucket_conf('tag')
    load_mocks(conf)
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        handle_webhook(test_name)

    # Negative tests
    test_name = 'test_bitbucket_invalid_rev'
    conf['payload']['push']['changes'][0]['new']['name'] = 'test'
    conf['payload_json'] = json.dumps(conf['payload'])
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        try:
            handle_webhook(test_name)
        except HTTPException as e:
            assert e.code == 403
            assert e.description == ('webhook request doesn\'t match its Cloud Deploy configuration: test_'
                                     'bitbucket_invalid_rev. error: invalid revision.')

    test_name = 'test_github_invalid_payload'
    conf = load_github_conf()
    del conf['payload']['repository']
    conf['payload_json'] = json.dumps(conf['payload'])
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        try:
            handle_webhook(test_name)
        except HTTPException as e:
            assert e.code == 422
            assert e.description == 'invalid webhook request payload: \'repository\''


@patch('webhooks.webhook_handler.post_internal')
@patch('webhooks.parsers.base.get_app')
@patch('webhooks.webhook_handler.get_webhook')
def test_webhook_gitlab(get_webhook, get_app, post_internal):
    conf = load_gitlab_conf()
    app = Flask(__name__)

    # Overwrite DB related function's behavior
    def load_mocks(conf):
        get_app.return_value = conf['app']
        get_webhook.return_value = conf['webhook']
        post_internal.return_value = mock_job_post()

    # Positive tests
    test_name = 'test_gitlab_simple'
    load_mocks(conf)
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        handle_webhook(test_name)

    test_name = 'test_gitlab_secret'
    conf['webhook']['secret_token'] = 'test'
    conf['headers']['X-Gitlab-Token'] = 'test'
    load_mocks(conf)
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        handle_webhook(test_name)

    test_name = 'test_gitlab_merge'
    conf = load_gitlab_conf('merge')
    load_mocks(conf)
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        handle_webhook(test_name)

    test_name = 'test_gitlab_tag'
    conf = load_gitlab_conf('tag')
    load_mocks(conf)
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        handle_webhook(test_name)

    # Negative tests
    test_name = 'test_gitlab_invalid_rev'
    conf = load_gitlab_conf()
    conf['webhook']['rev'] = 'test'
    load_mocks(conf)
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        try:
            handle_webhook(test_name)
        except HTTPException as e:
            assert e.code == 403
            assert e.description == ('webhook request doesn\'t match its Cloud Deploy configuration: test_'
                                     'gitlab_invalid_rev. error: invalid revision.')

    test_name = 'test_gitlab_invalid_payload'
    conf = load_gitlab_conf()
    del conf['payload']['repository']
    conf['payload_json'] = json.dumps(conf['payload'])
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        try:
            handle_webhook(test_name)
        except HTTPException as e:
            assert e.code == 422
            assert e.description == 'invalid webhook request payload: \'repository\''

    test_name = 'test_gitlab_invalid_secret'
    conf = load_gitlab_conf()
    conf['webhook']['secret_token'] = 'test'
    load_mocks(conf)
    with app.test_request_context('/webhook/' + test_name, method='POST', headers=conf['headers'], data=conf['payload_json']):
        try:
            handle_webhook(test_name)
        except HTTPException as e:
            assert e.code == 403
            assert e.description == ('webhook request doesn\'t match its Cloud Deploy configuration: test_'
                                     'gitlab_invalid_secret. error: invalid secret.')
