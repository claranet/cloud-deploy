jobs_schema = {
'command': {'type':'string', 'allowed':['deploy','maintenance'],'required': True},
'timestamp':{'type':'datetime','required': True},
'parameters': {
	'type':'dict',
	'schema': {
        'options' : {'type':'list', 'items':[{'type':'string'}]},
        'app_id' : {'type': 'integer', 'required': True},
		'modules' : {'type':'dict',
			'schema': {
				'name' : {'type':'string'},
				'rev'  : {'type':'string', 'default':'HEAD'}
			}
		}
	}

},
'status':{'type':'list', 'readonly':True, 'allowed':['pending','done','deleted']}
# TODO est ce que nous avons besoin du allowed alors ?

}

jobs = {
	'item_title': 'job',
	'schema' :jobs_schema
}

