jobs_schema = {
'command': {'type':'string', 'allowed':['deploy','maintenance'],'required': True},
'app_id' : {'type': 'string', 'regex':'^[a-f0-9]{24}$','required': True},
'status':{'type':'list', 'readonly':True},
'user': {'type':'string','required':True},
'parameters': {
	'type':'dict',
	'schema': {
        'options' : {'type':'list', 'items':[{'type':'string'}]},
		'modules' : {'type':'dict',
			'schema': {
				'name' : {'type':'string'},
				'rev'  : {'type':'string', 'default':'HEAD'}
			}
		}
	}

}

}

jobs = {
	'item_title': 'job',
	'schema' :jobs_schema
}


