jobs_schema = {
'command': {'type':'string', 'allowed':['deploy','maintenance'],'required': True},
'app_id' : {'type': 'string', 'regex':'^[a-f0-9]{24}$','required': True},
'job_id' : {'type': 'string', 'regex': '^[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}$', 'readonly': True},
'status':{'type':'list', 'readonly':True},
'user': {'type':'string','required':True},
'parameters': {
	'type':'dict',
	'schema': {
        'options' : {'type':'list', 'schema':{'type':'string'}},
		'modules' : {'type':'list',
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


