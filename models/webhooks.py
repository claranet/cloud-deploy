from .jobs import JOB_COMMANDS

webhook_schema = {
    'app_id': {
        'type': 'objectid',
        'required': True,
        'data_relation': {
            'resource': 'apps',
            'field': '_id',
            'embeddable': True
        }
    },
    'module': {
        'type': 'string'
    },
    'rev': {
        'type': 'string',
        'required': True
    },
    'events': {
        'type': 'list',
        'required': True,
        'schema': {
            'type': 'string',
            'required': True,
            'allowed': ['push', 'tag', 'merge']
        },
    },
    'commands': {
        'type': 'list',
        'required': True,
        'schema': {
            'type': 'string',
            'required': True,
            'allowed': JOB_COMMANDS
        },
    },
    'secret_token': {
        'type': 'string'
    },
    'options': {
        'type': 'dict'
    },
}

webhooks = {
    'datasource': {
        'source': 'webhooks'
    },
    'item_title': 'webhook',
    'schema': webhook_schema,
    'url': 'webhooks'
}
