# Let's just use the local mongod instance. Edit as needed.

# Please note that MONGO_HOST and MONGO_PORT could very well be left
# out as they already default to a bare bones local 'mongod' instance.
MONGO_HOST = 'localhost'
MONGO_PORT = 27017
#MONGO_USERNAME = 'user'
#MONGO_PASSWORD = 'user'
MONGO_DBNAME = 'apitest'

# Enable reads (GET), inserts (POST) and DELETE for resources/collections
# (if you omit this line, the API will default to ['GET'] and provide
# read-only access to the endpoint).
RESOURCE_METHODS = ['GET', 'POST', 'DELETE']

# Enable reads (GET), edits (PATCH), replacements (PUT) and deletes of
# individual items  (defaults to read-only item access).
ITEM_METHODS = ['GET', 'PATCH', 'PUT', 'DELETE']

jobs_schema = {
'command': {'type':'list', 'allowed':['deploy'],'required': True},
'timestap':{'type':'datetime','required': True}
'parameters': {
	'type':'dict',
	'schema': {
		options : {'type':'string'},
		app_id : {'type': 'integer'},
		module : {'type':'dict',
			'schema': {
				name : {'type':'string'},
				rev  : {'type':'string', 'default':'HEAD'}
			}
		} 
	}

},
'status':{'type':'list', 'allowed':['pending','done','deleted']}

}

jobs = {
	'item_title': 'job',
	'schema' :jobs_schema
}

DOMAIN = {
    'jobs': jobs
}

