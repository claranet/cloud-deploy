deploy_history_schema = {
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

deploy_histories = {'item_title': 'deploy_history', 'schema': deploy_history_schema}
