available = {'type': 'dict',
             'allowed': [
                 {'rds-mysql': {'type': 'dict',
                                'schema': {
                                    'name': {'type': 'string', },
                                    'hostname': {'type': 'string'},
                                    'port': {'type': 'integer',
                                             'min': 1,
                                             'max': 65535},
                                    'database': {'type': 'string'},
                                    'login': {'type': 'string'},
                                    'password': {'type': 'string'}
                                }}}, {'redis':
                                      {'type': 'dict',
                                       'schema': {
                                           'name': {'type': 'string', },
                                           'uri': {'type': 'string'}
                                       }}}
             ]}
