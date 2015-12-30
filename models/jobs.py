jobs_schema = {
    'command': {
        'type': 'string',
        'required': True,
        'allowed': ['deploy', 'buildimage', 'maintenance', 'rollback',
                    'createinstance', 'destroyinstance',
                    'updatelifecyclehooks']
    },
    'app_id': {
        'type': 'objectid',
        'required': True,
        'data_relation': {
            'resource': 'apps',
            'field': '_id',
            'embeddable': True
        }
    },
    'status': {
        'type': 'string',
        'readonly': True
    },
    'message': {
        'type': 'string',
        'readonly': True
    },
    'log_id': {
        'type': 'string',
        'readonly': True
    },
    'user': {
        'type': 'string'
    },
    'instance_type': {
        'type': 'string',
        'default': 't2.micro'
    },
    'options': {
        'type': 'list',
        'schema': {
            'type': 'string'
        }
    },
    'modules': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {
                    'type': 'string',
                    'required': True
                },
                'rev': {
                    'type': 'string',
                    'default': 'HEAD'
                },
                'deploy_id': {
                    'type': 'string',
                    'readonly': True
                }
            }
        }
    }
}

jobs = {'item_title': 'job', 'schema': jobs_schema}

CANCELLABLE_JOB_STATUSES = ['init']
DELETABLE_JOB_STATUSES = ['cancelled', 'done', 'failed', 'aborted']
JOB_STATUSES = ['init', 'cancelled', 'done', 'failed', 'aborted']
