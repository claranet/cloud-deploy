import os
from models import jobs
from models import apps
from models import deployments
from models import job_enqueueings
from models import webhooks
from botosts.aws_connection import AWSConnection

from ghost_tools import config, CURRENT_REVISION_NAME

# required. See http://swagger.io/specification/#infoObject for details.
SWAGGER_INFO = {
    'title': 'Claranet Cloud Deploy (Ghost)',
    'version': CURRENT_REVISION_NAME,
    'description': 'The Claranet Cloud Deploy (Ghost) API by Morea, Claranet Public Cloud Practice',
    'termsOfService': 'Copyright (C) Claranet - All Rights Reserved',
    'contact': {
        'name': 'Morea, Claranet Public Cloud Practice',
        'url': 'http://www.claranet.fr/'
    },
    'license': {
        'name': 'Apache License 2.0',
        'url': 'https://github.com/claranet/cloud-deploy/blob/stable/LICENSE',
    }
}

# CORS settings for Swagger UI
X_DOMAINS = [
    'http://docs.cloud-deploy.io',
    'https://docs.cloud-deploy.io',
    'http://docs.cloudeploy.io',
    'https://docs.cloudeploy.io',
    'http://editor.swagger.io',
]
X_HEADERS = ['Authorization', 'Content-Type', 'If-Match']

API_NAME = 'GHOST API'

# Let's just use the local mongod instance. Edit as needed.

# Please note that MONGO_HOST and MONGO_PORT could very well be left
# out as they already default to a bare bones local 'mongod' instance.
# Get env var first (e.g. from docker-compose and the like), then config file, then default
MONGO_HOST = os.getenv('MONGO_HOST', config.get('mongo_host', 'localhost'))
MONGO_PORT = 27017
#MONGO_USERNAME = 'user'
#MONGO_PASSWORD = 'user'
MONGO_DBNAME = 'apitest'
MONGO_QUERY_BLACKLIST = ['$where']

# RQ Workers params
RQ_JOB_TIMEOUT = config.get('rq_worker_job_timeout', 3600)

REDIS_HOST = os.getenv('REDIS_HOST', config.get('redis_host', 'localhost'))

# Enable reads (GET) and inserts (POST) for resources/collections
# (if you omit this line, the API will default to ['GET'] and provide
# read-only access to the endpoint).
RESOURCE_METHODS = ['GET', 'POST']

# Enable reads (GET), edits (PATCH), replacements (PUT) and deletes of
# individual items  (defaults to read-only item access).
ITEM_METHODS = ['GET', 'PATCH', 'PUT', 'DELETE']

# EVE Pagination
PAGINATION_DEFAULT = config.get('eve_pagination_default', 23)
PAGINATION_LIMIT = config.get('eve_pagination_limit', 200)

# API BASE URL
API_BASE_URL = os.getenv('API_BASE_URL', config.get('api_base_url', 'http://localhost:5000'))

DOMAIN = {
    'job_enqueueings': job_enqueueings.job_enqueueings,
    'jobs': jobs.jobs,
    'apps': apps.apps,
    'deployments': deployments.deployments,
    'webhooks': webhooks.webhooks,
}

cloud_connections = {
    'aws': AWSConnection,
    'azure': 'NotYetSupported',
    'google': 'NotYetSupported'
}
# Default cloud provider
DEFAULT_PROVIDER = 'aws'

DEBUG = True

VERSIONING = True
