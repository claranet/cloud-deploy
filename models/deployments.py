deployment_schema = {
    'app_id': {
        'type': 'string', 'readonly': True
    },
    'job_id': {
        'type': 'string', 'readonly': True
    },
    'module': {
        'type': 'string', 'readonly': True
    },
    'commit': {
        'type': 'string', 'readonly': True
    },
    'commit_message': {
        'type': 'string', 'readonly': True
    },
    'timestamp': {
        'type': 'string', 'readonly': True
    },
    'package': {
        'type': 'string', 'readonly': True
    },
    'module_path': {
        'type': 'string', 'readonly': True
    }
}

deployments = {
    'datasource': {
        'source': 'deploy_histories'
    },
    'item_title': 'deployment',
    'schema': deployment_schema,
    'resource_methods': ['GET'],
    'item_methods': ['GET']
}
