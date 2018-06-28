from flask import Flask, json
from mock import patch
from werkzeug.exceptions import HTTPException

from run import pre_insert_webhook_invocation
from helpers import mock_job_post
from helpers_webhook import gen_webhook_url, load_bitbucket_conf, load_github_conf, load_gitlab_conf
from helpers_webhook import get_webhook_id


# Global variables common to all tests
webhook_id = get_webhook_id()
webhook_url = gen_webhook_url()


@patch('run.Validator.errors')
@patch('webhooks.webhook_handler.post_internal')
@patch('webhooks.parsers.base.get_app')
@patch('webhooks.webhook_handler.get_webhook')
def test_webhook_github(get_webhook, get_app, post_internal, errors):
    app = Flask(__name__)

    # Overwrite DB related function's behavior
    def load_mocks(conf):
        get_app.return_value = conf['app']
        get_webhook.return_value = conf['webhook']
        post_internal.return_value = mock_job_post()
        errors.keys.return_value = {}

    # Positive tests
    # test_github_push
    conf = load_github_conf()
    load_mocks(conf)
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            pre_insert_webhook_invocation(conf['invocation'])

    # test_github_merge
    conf = load_github_conf('merge')
    load_mocks(conf)
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            pre_insert_webhook_invocation(conf['invocation'])

    # test_github_tag
    conf = load_github_conf('tag')
    load_mocks(conf)
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            pre_insert_webhook_invocation(conf['invocation'])

    # Negative tests
    conf = load_github_conf()
    # test_github_invalid_rev
    conf['webhook']['rev'] = 'test'
    load_mocks(conf)
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            pre_insert_webhook_invocation(conf['invocation'])
            assert conf['invocation'][0]['status']['code'] == 403
            assert conf['invocation'][0]['status']['message'] == ('Webhook request doesn\'t match its Cloud Deploy configuration: '
                                                                  '{webhook_id}. error: invalid revision.'.format(webhook_id=webhook_id))

    # test_github_invalid_payload
    conf = load_github_conf()
    del conf['payload']['repository']
    conf['payload_json'] = json.dumps(conf['payload'])
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            try:
                pre_insert_webhook_invocation(conf['invocation'])
            except HTTPException as e:
                assert e.code == 422
                assert e.description == 'Invalid webhook request payload: \'repository\''


@patch('run.Validator.errors')
@patch('webhooks.webhook_handler.post_internal')
@patch('webhooks.parsers.base.get_app')
@patch('webhooks.webhook_handler.get_webhook')
def test_webhook_bitbucket(get_webhook, get_app, post_internal, errors):
    conf = load_bitbucket_conf()
    app = Flask(__name__)

    # Overwrite DB related function's behavior
    def load_mocks(conf):
        get_app.return_value = conf['app']
        get_webhook.return_value = conf['webhook']
        post_internal.return_value = mock_job_post()
        errors.keys.return_value = {}

    # Positive tests
    load_mocks(conf)
    # test_bitbucket_simple
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            pre_insert_webhook_invocation(conf['invocation'])

    # test_bitbucket_merge
    conf = load_bitbucket_conf('merge')
    load_mocks(conf)
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            pre_insert_webhook_invocation(conf['invocation'])

    # test_bitbucket_tag
    conf = load_bitbucket_conf('tag')
    load_mocks(conf)
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            pre_insert_webhook_invocation(conf['invocation'])

    # Negative tests
    # test_bitbucket_invalid_rev
    conf['payload']['push']['changes'][0]['new']['name'] = 'test'
    conf['payload_json'] = json.dumps(conf['payload'])
    with app.test_request_context(gen_webhook_url(), method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            pre_insert_webhook_invocation(conf['invocation'])
            assert conf['invocation'][0]['status']['code'] == 403
            assert conf['invocation'][0]['status']['message'] == ('Webhook request doesn\'t match its Cloud Deploy configuration: '
                                                                  '{webhook_id}. error: invalid revision.'.format(webhook_id=webhook_id))

    # test_github_invalid_payload
    conf = load_github_conf()
    del conf['payload']['repository']
    conf['payload_json'] = json.dumps(conf['payload'])
    with app.test_request_context(gen_webhook_url(), method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            try:
                pre_insert_webhook_invocation(conf['invocation'])
            except HTTPException as e:
                assert e.code == 422
                assert e.description == 'Invalid webhook request payload: \'repository\''


@patch('run.Validator.errors')
@patch('webhooks.webhook_handler.post_internal')
@patch('webhooks.parsers.base.get_app')
@patch('webhooks.webhook_handler.get_webhook')
def test_webhook_gitlab(get_webhook, get_app, post_internal, errors):
    conf = load_gitlab_conf()
    app = Flask(__name__)

    # Overwrite DB related function's behavior
    def load_mocks(conf):
        get_app.return_value = conf['app']
        get_webhook.return_value = conf['webhook']
        post_internal.return_value = mock_job_post()
        errors.keys.return_value = {}

    # Positive tests
    # test_gitlab_simple
    load_mocks(conf)
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            pre_insert_webhook_invocation(conf['invocation'])

    # test_gitlab_secret
    conf['webhook']['secret_token'] = 'test'
    conf['headers']['X-Gitlab-Token'] = 'test'
    load_mocks(conf)
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            pre_insert_webhook_invocation(conf['invocation'])

    # test_gitlab_merge
    conf = load_gitlab_conf('merge')
    load_mocks(conf)
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            pre_insert_webhook_invocation(conf['invocation'])

    # test_gitlab_tag
    conf = load_gitlab_conf('tag')
    load_mocks(conf)
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            pre_insert_webhook_invocation(conf['invocation'])

    # Negative tests
    # test_gitlab_invalid_rev
    conf = load_gitlab_conf()
    conf['webhook']['rev'] = 'test'
    load_mocks(conf)
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            pre_insert_webhook_invocation(conf['invocation'])
            assert conf['invocation'][0]['status']['code'] == 403
            assert conf['invocation'][0]['status']['message'] == ('Webhook request doesn\'t match its Cloud Deploy configuration: '
                                                                  '{webhook_id}. error: invalid revision.'.format(webhook_id=webhook_id))

    # test_gitlab_invalid_payload
    conf = load_gitlab_conf()
    del conf['payload']['repository']
    conf['payload_json'] = json.dumps(conf['payload'])
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            try:
                pre_insert_webhook_invocation(conf['invocation'])
            except HTTPException as e:
                assert e.code == 422
                assert e.description == 'Invalid webhook request payload: \'repository\''

    # test_gitlab_invalid_secret
    conf = load_gitlab_conf()
    conf['webhook']['secret_token'] = 'test'
    load_mocks(conf)
    with app.test_request_context(webhook_url, method='POST', headers=conf['headers'], data=conf['payload_json']):
        with patch('run.request.view_args', {'webhook_id': webhook_id}):
            pre_insert_webhook_invocation(conf['invocation'])
            assert conf['invocation'][0]['status']['code'] == 403
            assert conf['invocation'][0]['status']['message'] == ('Webhook request doesn\'t match its Cloud Deploy configuration: '
                                                                  '{webhook_id}. error: invalid secret.'.format(webhook_id=webhook_id))
