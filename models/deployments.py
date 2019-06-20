deployment_schema = {
    'app_id': {
        'type': 'objectid',
        'readonly': True,
        'data_relation': {
            'resource': 'apps',
            'field': '_id',
            'embeddable': True
        }
    },
    'job_id': {
        'type': 'objectid',
        'readonly': True,
        'data_relation': {
            'resource': 'jobs',
            'field': '_id',
            'embeddable': True
        }
    },
    'module': {
        'type': 'string',
        'readonly': True
    },
    'revision': {
        'type': 'string',
        'readonly': True
    },
    'commit': {
        'type': 'string',
        'readonly': True
    },
    'commit_message': {
        'type': 'string',
        'readonly': True
    },
    'timestamp': {
        'type': 'string',
        'readonly': True
    },
    'package': {
        'type': 'string',
        'readonly': True
    },
    'module_path': {
        'type': 'string',
        'readonly': True
    }
}

deployments = {
    'datasource': {
        'source': 'deploy_histories'
    },
    'item_title': 'deployment',
    'schema': deployment_schema,
    'resource_methods': ['GET'],
    'item_methods': ['GET'],
    'mongo_indexes': {
        'app_id-modules-timestamp': [('app_id', 1), ('module', 1), ('timestamp', -1)]
    }
}
