import instance_role
from jobs import LOG_NOTIFICATION_JOB_STATUSES
import resources
import tags
import volumes

APPS_DEFAULT = {
    'modules.source.mode': 'symlink',
    'modules.source.protocol': 'git',
}

apps_schema = {
    'name': {
        'type': 'string',
        'regex': '^[a-zA-Z0-9_.+-]*$',
        'required': True
    },
    'env': {
        'type': 'string',
        'regex': '^[a-z0-9\-\_]*$',
        'required': True
    },
    'role': {
        'type': 'string',
        'regex': '^[a-z0-9\-\_]*$',
        'required': True
    },
    'description': {
        'type': 'string',
        'required': False
    },
    'assumed_account_id': {
        'type': 'string',
        'regex': '^[a-zA-Z0-9_.+-]*$',
        'required': False
    },
    'assumed_role_name': {
        'type': 'string',
        'regex': '^[a-zA-Z0-9_.+-]*$',
        'required': False
    },
    'assumed_region_name': {
        'type': 'string',
        'regex': '^[a-zA-Z0-9_.+-]*$',
        'required': False
    },
    'region': {'type': 'string'},
    'instance_type': {'type': 'string'},
    'instance_monitoring' : {'type': 'boolean', 'required': False},
    'lifecycle_hooks': {
        'type': 'dict',
        'schema': {
            'pre_buildimage': {'type': 'string'},
            'post_buildimage': {'type': 'string'},
            'pre_bootstrap': {'type': 'string'},
            'post_bootstrap': {'type': 'string'},
        }
    },
    'blue_green': {
        'type': 'dict',
        'schema': {
            'enable_blue_green': {'type': 'boolean', 'required': False},
            'hooks': {
                'type': 'dict',
                'schema': {
                    'pre_swap': {'type': 'string'},
                    'post_swap': {'type': 'string'},
                }
            },
            'color': {'type': 'string', 'allowed': ['blue', 'green'], 'required': False},
            'is_online': {'type': 'boolean', 'required': False},
            'alter_ego_id': {
                'readonly': True,
                'type': 'objectid',
                'data_relation': {
                    'resource': 'apps',
                    'field': '_id',
                    'embeddable': False
                }
            }
        }
    },
    'features': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {
                    'type': 'string',
                    'regex': '^[a-zA-Z0-9\.\-\_]*$',
                    'required': True
                },
                'version': {
                    'type': 'string',
                    'regex': '^[a-zA-Z0-9\.\-\_\/:~\+=\,]*$',
                    'required': False
                },
                'provisioner': {
                    'type': 'string',
                    'regex': '^[a-zA-Z0-9]*$',
                    'required': False
                },
                'parameters': {
                    'type': 'dict',
                    'allow_unknown': True,
                }
            }
        }
    },
    'env_vars': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'var_key': {
                    'type': 'string',
                    'regex': '^(?!GHOST|ghost)[a-zA-Z_]+[a-zA-Z0-9_]*$',
                    'required': False
                },
                'var_value': {
                    'type': 'string',
                    'required': False
                }
            }
        }
    },
    'ami': {'type': 'string',
            'regex': '^ami-[a-z0-9]*$',
            'readonly': True},
    'vpc_id': {
        'type': 'string',
        'regex': '^vpc-[a-z0-9]*$',
        'required': True
    },
    'modules': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'initialized': {'type': 'boolean',
                                'readonly': True},
                'name': {'type': 'string',
                         'regex': '^[a-zA-Z0-9\.\-\_]*$',
                         'required': True},
                'source': {
                    'type': 'dict',
                    'schema': {
                        'protocol': {
                            'type': 'string',
                            'required': False,
                            'default': APPS_DEFAULT['modules.source.protocol'],
                            'allowed': ['git', 's3'],
                        },
                        'url': {
                            'type': 'string',
                            'required': False,
                        },
                        'mode': {
                            'type': 'string',
                            'required': False,
                            'default': APPS_DEFAULT['modules.source.mode'],
                            'allowed': ['symlink'],
                        },
                    },
                },
                'git_repo': {'type': 'string',
                             'required': False},
                'scope': {
                    'type': 'string',
                    'required': True,
                    'allowed': ['system', 'code']
                },
                'uid': {'type': 'integer', 'min': 0},
                'gid': {'type': 'integer', 'min': 0},
                'build_pack': {'type': 'string'},
                'pre_deploy': {'type': 'string'},
                'post_deploy': {'type': 'string'},
                'after_all_deploy': {'type': 'string'},
                'path': {'type': 'string',
                         'regex': '^(/[a-zA-Z0-9\.\-\_]+)+$',
                         'required': True},
                'last_deployment': {
                    'readonly': True,
                    'type': 'objectid',
                    'data_relation': {
                        'resource': 'deployments',
                        'field': '_id',
                        'embeddable': True
                    }
                }
            }
        }
    },
    'log_notifications': {
        'type': 'list',
        'coerce': lambda l: [{'email': v, 'job_states': ['*']} if isinstance(v, basestring) else v for v in l],
        'schema': {
            'type': 'dict',
            'schema': {
                'email': {
                    'type': 'string',
                    'regex': '^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
                },
                'job_states': {
                    'type': 'list',
                    'schema': {
                        'type': 'string',
                        'allowed': LOG_NOTIFICATION_JOB_STATUSES + ['*'],
                        'default': '*'
                    }
                }
            }
        }
    },
    'autoscale': {
        'type': 'dict',
        'schema': {
            'min': {'type': 'integer', 'min': 0},
            'max': {'type': 'integer', 'min': 0},
            'enable_metrics': {'type': 'boolean', 'required': False},
            'name': {'type': 'string'}
        }
    },
    'safe-deployment': {
        'type': 'dict',
        'schema': {
            'load_balancer_type' : {'type': 'string'},
            'wait_after_deploy' : {'type': 'integer', 'min': 0},
            'wait_before_deploy' : {'type': 'integer', 'min': 0},
            'app_tag_value': {'type': 'string', 'required': False},
            'ha_backend': {'type': 'string', 'required': False},
            'api_port': {'type': 'integer', 'required': False}
        }
    },
    'build_infos': {
        'type': 'dict',
        'schema': {
            'ssh_username': {'type': 'string',
                             'regex': '^[a-z\_][a-z0-9\_\-]{0,30}$',
                             'required': True},
            'source_ami': {'type': 'string',
                           'regex': '^ami-[a-z0-9]*$',
                           'required': True},
            'ami_name': {'type': 'string',
                         'readonly': True},
            'source_container_image': {'type': 'string',
                          'regex': '^(().)*$',
                          'required': False
                          },
            'container_image': {'type': 'string',
                          'readonly': True
                          },
            'subnet_id': {'type': 'string',
                          'regex': '^subnet-[a-z0-9]*$',
                          'required': True}
        }
    },
    'resources': {'type': 'list',
                  'schema': resources.available},
    'environment_infos': {'type': 'dict',
                          'schema': {
                              'security_groups': {'type': 'list',
                                                  'schema':
                                                  {'type': 'string',
                                                   'regex': '^sg-[a-z0-9]*$'}},
                              'subnet_ids': {'type': 'list',
                                             'schema': {'type': 'string',
                                                        'regex':
                                                        '^subnet-[a-z0-9]*$'}},
                              'instance_profile':
                              {'type': 'string',
                               'regex': '^[a-zA-Z0-9\+\=\,\.\@\-\_]{1,128}$'},
                              'key_name': {'type': 'string',
                                           'regex': '^[\x00-\x7F]{1,255}$'},
                              'public_ip_address': {'type': 'boolean', 'required': False, 'default':True},
                              'root_block_device':
                              {'type': 'dict',
                               'schema': {
                                   'size': {'type': 'integer', 'min': 20},
                                   'name': {'type': 'string',
                                            'regex': '^$|^(/[a-z0-9]+/)?[a-z0-9]+$'}
                               }},
                              'instance_tags':
                              {'type': 'list',
                               'required': False,
                               'schema': tags.block
                              },
                              'optional_volumes': {'type': 'list',
                                                   'required': False,
                                                   'schema': volumes.block}
                          }},
    'user': {'type': 'string'},
    'pending_changes': {
        'type': 'list',
        'required': False,
        'schema': {
            'type': 'dict',
            'schema': {
                'field': {
                    'type': 'string',
                    'regex': '[a-zA-Z_]+[a-zA-Z0-9_]*$',
                    'required': False
                },
                'user': {
                    'type': 'string',
                    'required': False
                },
                'updated': {
                    'type': 'datetime',
                    'required': False
                },
           },
        },
    },
}

apps = {
    'datasource': {
        'source': 'apps'
    },
    'item_title': 'app',
    'schema': apps_schema,
    'mongo_indexes': {
         'name-role-env-blue_green.color': [('name', 1), ('role', 1), ('env', 1), ('blue_green.color', 1)],
    }
}
