from models import jobs
from models import apps
from models import deployments
from models import job_enqueueings

API_NAME = 'GHOST API'

# Let's just use the local mongod instance. Edit as needed.

# Please note that MONGO_HOST and MONGO_PORT could very well be left
# out as they already default to a bare bones local 'mongod' instance.
MONGO_HOST = 'localhost'
MONGO_PORT = 27017
#MONGO_USERNAME = 'user'
#MONGO_PASSWORD = 'user'
MONGO_DBNAME = 'apitest'

# Enable reads (GET) and inserts (POST) for resources/collections
# (if you omit this line, the API will default to ['GET'] and provide
# read-only access to the endpoint).
RESOURCE_METHODS = ['GET', 'POST']

# Enable reads (GET), edits (PATCH), replacements (PUT) and deletes of
# individual items  (defaults to read-only item access).
ITEM_METHODS = ['GET', 'PATCH', 'PUT', 'DELETE']

# Quick pagination fix
PAGINATION_DEFAULT = 42

DOMAIN = {
    'job_enqueueings': job_enqueueings.job_enqueueings,
    'jobs': jobs.jobs,
    'apps': apps.apps,
    'deployments': deployments.deployments
}

DEBUG = True

VERSIONING = True
