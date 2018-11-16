from flask import json
from datetime import datetime


event_to_header = {
    'github': {
        'push': 'push',
        'tag': 'create',
        'merge': 'pull_request',
    },
    'bitbucket': {
        'push': 'repo:push',
        'tag': 'repo:push',
        'merge': 'pullrequest:fulfilled',
    },
    'gitlab': {
        'push': 'Push Hook',
        'tag': 'Tag Push Hook',
        'merge': 'Merge Request Hook',
    }
}


def base_invocation_item():
    return [{
        '_created': datetime.now(),
        '_etag ': '1c501c0ffcd8212de99e44e1971d6568f19ffb40',
        '_id': '5b1e82bae617250001845a81',
        '_latest_version': 1,
        '_updated': datetime.now(),
        '_version': 1,
        'bad_data': True
    }]


def base_app():
    return {
        'name': 'name',
        'env': 'env',
        'role': 'role',
        'modules': [{
            "name": "wordpress",
            "git_repo": "",
            "scope": "code",
            "path": "/var/www"
        }]
    }


def base_webhook():
    return {
        "app_id": "test",
        "module": "wordpress",
        "rev": "master",
        "commands": ["deploy"],
        "events": [],
        "deployment_strategy": "serial"
    }


def load_github_conf(event='push'):
    conf = dict()

    # Basic conf
    conf['app'] = base_app()
    conf['webhook'] = base_webhook()
    conf['invocation'] = base_invocation_item()

    # Customs
    conf['app']['modules'][0]['git_repo'] = 'git@github.com:test/test.git'
    conf['webhook']['events'] = event

    with open('tests/webhook_data/github_{event}_payload.json'.format(event=event)) as f:
        conf['payload'] = json.load(f)

    conf['payload_json'] = json.dumps(conf['payload'])

    conf['headers'] = {
        'Content-Type': 'application/json',
        'X-GitHub-Event': event_to_header['github'][event],
        'User-Agent': 'GitHub-Hookshot/72cb439',
    }

    return conf


def load_bitbucket_conf(event='push'):
    conf = dict()

    # Basic conf
    conf['app'] = base_app()
    conf['webhook'] = base_webhook()
    conf['invocation'] = base_invocation_item()

    # Customs
    conf['app']['modules'][0]['git_repo'] = 'git@bitbucket.org:test/test.git'
    conf['webhook']['events'] = event

    with open('tests/webhook_data/bitbucket_{event}_payload.json'.format(event=event)) as f:
        conf['payload'] = json.load(f)

    conf['payload_json'] = json.dumps(conf['payload'])

    conf['headers'] = {
        'Content-Type': 'application/json',
        'X-Event-Key': event_to_header['bitbucket'][event],
        'User-Agent': 'Bitbucket-Webhooks/2.0',
    }

    return conf


def load_gitlab_conf(event='push'):
    conf = dict()

    # Basic conf
    conf['app'] = base_app()
    conf['webhook'] = base_webhook()
    conf['invocation'] = base_invocation_item()

    # Customs
    conf['app']['modules'][0]['git_repo'] = 'git@gitlab.com:test/test.git'
    conf['webhook']['events'] = event

    with open('tests/webhook_data/gitlab_{event}_payload.json'.format(event=event)) as f:
        conf['payload'] = json.load(f)

    conf['payload_json'] = json.dumps(conf['payload'])

    conf['headers'] = {
        'Content-Type': 'application/json',
        'X-Gitlab-Event': event_to_header['gitlab'][event]
    }

    return conf


def get_webhook_id():
    return '5b1e82bae617250001845a81'


def gen_webhook_url(webhook_id='5b1e82bae617250001845a81'):
    return 'webhooks/{id}/invocations'.format(id=webhook_id)