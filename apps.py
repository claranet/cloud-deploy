import env
import code_deploy
import instance_role
import aws_data
import ressources

apps_schema = {
    'name': {
        'type': 'string', 'regex': '^[a-zA-Z0-9_.+-]*$', 'required': True
    },
    'region': {'type': 'string', 'allowed': ['us-east-1', 'eu-west-1']},
    'instance_type': {'type': 'string', 'allowed': aws_data.instance_type},
    'env': {'type': 'string', 'allowed': env.env, 'required': True},
    'features': {
        'type': 'list', 'schema': {
            'type': 'dict', 'schema': {
                'name': {
                    'type': 'string', 'regex': '^[a-zA-Z0-9\.\-\_]*$',
                    'required': True
                }, 'version': {
                    'type': 'string', 'regex': '^[a-zA-Z0-9\.\-\_]*$',
                    'required': False
                }
            }
        }
    },
    'role': {
        'type': 'string', 'allowed': instance_role.role, 'required': True
    },
    'ami': {'type': 'string', 'regex': '^ami-[a-z0-9]*$', 'readonly': True},
    'vpc_id': {
        'type': 'string', 'regex': '^vpc-[a-z0-9]*$', 'required': True
    },
    'modules': {
        'type': 'list', 'schema': {
            'type': 'dict', 'schema': {
                'initialized': {'type': 'boolean', 'readonly': True
                        }, 'name': {'type': 'string', 'required': True
                 }, 'git_repo': {'type': 'string', 'required': True
                     }, 'scope': {
                         'type': 'string', 'required': True, 'allowed': [
                             'system', 'code'
                         ]
                     }, 'build_pack': {'type': 'string'
                      }, 'pre_deploy': {'type': 'string'
                      }, 'post_deploy': {'type': 'string'
                       }, 'path': {'type': 'string', 'required': True}
            }
        }
    },
    'log_notifications': {
        'type': 'list', 'schema': {
            'type': 'string', 'regex':
            '^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        }
    },
    'autoscale': {
        'type': 'dict', 'schema': {
            'min': {'type': 'integer', 'min': 0
                }, 'max': {'type': 'integer', 'min': 1
                }, 'current': {'type': 'integer'}, 'name': {'type': 'string'}
        }
    },
    'build_infos': {
        'type': 'dict', 'schema': {
            'ssh_username': {'type': 'string', 'required': True}, 'source_ami':
            {'type': 'string', 'regex': '^ami-[a-z0-9]*$', 'required': True
                        }, 'ami_name': {'type': 'string', 'required': True
                      }, 'subnet_id': {
                          'type': 'string', 'regex': '^subnet-[a-z0-9]*$',
                          'required': True
                      }
        }
    },
    # TODO solve storing password in cleartext
    'ressources': {'type': 'list', 'schema': ressources.available},
    'environment_infos': {
        'type': 'dict', 'schema': {
            'security_groups': {
                'type': 'list', 'schema': {
                    'type': 'string', 'regex': '^sg-[a-z0-9]*$'
                }
            }, 'subnet_ids': {
                'type': 'list', 'schema': {
                    'type': 'string', 'regex': '^subnet-[a-z0-9]*$'
                }
            }, 'instance_profile': {'type': 'string'
                              }, 'key_name': {'type': 'string'
                      }, 'root_block_device': {
                          'type': 'dict', 'schema': {
                              'size': {'type': 'integer'
                     }, 'name': {
                         'type': 'string', 'regex': '^/[a-z0-9]+/[a-z0-9]+$'
                     }
                          }
                      }
        }
    }
}

apps = {'item_title': 'app', 'schema': apps_schema}
