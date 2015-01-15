jobs_schema = {
"command": {"type":"string", "allowed":["deploy"],"required": True},
"timestamp":{"type":"datetime","required": True},
"parameters": {
	"type":"dict",
	"schema": {
		"options" : {"type":"string"},
		"app_id" : {"type": "integer"},
		"module" : {"type":"dict",
			"schema": {
				"name" : {"type":"string"},
				"rev"  : {"type":"string", "default":"HEAD"}
			}
		} 
	}

},
"status":{"type":"list", "allowed":["pending","done","deleted"]}

}

jobs = {
	'item_title': 'job',
	'schema' :jobs_schema
}
