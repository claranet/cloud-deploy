block = {'type': 'dict',
         'schema': {
             'device_name': {'type': 'string',
                             'regex': '^/dev/xvd[b-m]$',
                             'required': True},
             'volume_type': {'type': 'string',
                             'allowed': ['gp2', 'io1', 'standard'],
                             'required': True},
             'volume_size': {'type': 'integer',
                             'required': True},
             'iops': {'type': 'integer',
                      'required': False}
         }}
