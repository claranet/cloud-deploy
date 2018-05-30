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
        'type': 'string',
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
        'type': 'string',
    },
    'deployment_strategy': {
        'type': 'string',
        'required': True,
        'allowed': ['serial', 'parallel']
    },
    'safe_deployment_strategy': {
        'type': 'string',
        'allowed': ['1by1', '1/3', '25%', '50%']
    },
    'instance_type': {
        'type': 'string',
        'default': 't2.micro'
    },
}

webhooks = {
    'datasource': {
        'source': 'webhooks'
    },
    'item_title': 'webhook',
    'schema': webhook_schema
}
