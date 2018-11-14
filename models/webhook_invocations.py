webhook_invocation_schema = {
    'webhook_id': {
        'type': 'objectid',
        'required': True,
        'data_relation': {
            'resource': 'webhooks',
            'field': '_id',
            'embeddable': True
        }
    },
    'jobs': {
        'type': 'list',
        'schema': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'jobs',
                'field': '_id',
                'embeddable': True
            }
        }
    },
    'status': {
        'type': 'dict',
        'schema': {
            'code': {
                'type': 'integer'
            },
            'message': {
                'type': 'string'
            }
        }
    },
    'payload': {
        'type': 'string',
    }
}

webhook_invocations = {
    'datasource': {
        'source': 'webhook_invocations'
    },
    'item_title': 'webhook_invocation',
    'schema': webhook_invocation_schema,
    'url': 'webhooks/<regex("[a-f0-9]{24}"):webhook_id>/invocations',
    'resource_methods': ['GET', 'POST'],
    'resource_title': 'webhook_invocation',
    'public_methods': ['POST'],
    'public_item_methods': ['POST'],
    'allow_unknown': True
}

webhook_all_invocations = {
    'datasource': {
        'source': 'webhook_invocations'
    },
    'schema': webhook_invocation_schema,
    'url': 'webhooks/all/invocations',
    'resource_methods': ['GET'],
    'resource_title': 'webhook_invocation',
    'allow_unknown': True
}
