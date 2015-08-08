jobs_schema = {
    'command': {
        'type': 'string', 'required': True,
        'allowed': ['deploy', 'buildimage', 'maintenance', 'rollback', 'createinstance', 'destroyinstance']
    },
    'app_id': {
        'type': 'objectid', 'required': True,
        'data_relation': {
            'resource': 'apps',
            'field': '_id',
            'embeddable': True
        }
    },
    #FIXME: dup with _id, to remove?
    'job_id': {
        'type': 'objectid', 'readonly': True
    },
    'status': {
        'type': 'string', 'readonly': True
    },
    'log_id': {
        'type': 'string', 'readonly': True
    },
    'user': {
        'type': 'string'
    },
    'options': {
        'type': 'list', 'schema': {
            'type': 'string'
        }
    },
    'modules': {
        'type': 'list', 'schema': {
            'type': 'dict', 'schema': {
                'name': {
                    'type': 'string', 'required': True
                }, 'rev': {
                    'type': 'string', 'default': 'HEAD'
                }, 'deploy_id': {
                    'type': 'string', 'readonly': True
                }
            }
        }
    }
}

jobs = {'item_title': 'job', 'schema': jobs_schema}
