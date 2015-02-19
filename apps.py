import env
import code_deploy
import instance_role
import salt_features
import aws_data
import ressources

apps_schema = {
    'name': {'type': 'string', 'regex': '^[a-zA-Z0-9_.+-]*$', 'required':True },
    'aws_region': {'type': 'string', 'allowed':['us-east-1','eu-west-1']},
    'instance_type': {'type': 'string', 'allowed':aws_data.instance_type},
    'env': {'type': 'string', 'allowed':env.env, 'required':True},
    'features':{'type':'list', 'schema':salt_features.recipes},
    'role': {'type':'string', 'allowed':instance_role.role,'required':True},
    'ami': {'type':'string'},
    'ami_ref': {'type':'string'},
    'vpc': {'type':'string'},
    'modules': {'type':'list','schema':{ 'type':'dict', 'schema': {
        'initialized': {'type':'boolean', 'readonly':True},
        'name': {'type':'string', 'required':True},
        'git_repo': {'type':'string', 'required':True},
        'scope': {'type':'string', 'required':True,'allowed':['system','code']},
        #'code_deploy' : {'type':'dict', 'schema':code_deploy.code_deploy},
        'build_pack':{'type':'media'},
        'pre_deploy':{'type':'media'},
        'post_deploy':{'type':'media'},
        'path':{'type':'string', 'required':True}}}
    },
    'log_notifications' : {'type':'list','schema':{'type':'string',
        'regex':'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'}
    },
    'autoscale': { 'type': 'dict', 'schema': {
        '_min': {'type':'integer', 'min':0},
        '_max': {'type':'integer', 'min':1},
        'current': {'type':'integer'}
        }
    },
    # TODO solve storing password in cleartext
    'ressources': {'type':'list', 'schema':ressources.available}
}

apps = {
'item_title': 'app',
'schema': apps_schema
}


#def pre_GET_apps(request, lookup):
#    print 'A GET request on apps endpoint has just been received!'
