import flask
import mock
from mock import MagicMock
from run import pre_insert_app

@mock.patch('run.get_apps_db')
@mock.patch('run.request')
def test_application_insert(request, get_apps_db):
  apps_db = MagicMock()
  apps_db.find_one = MagicMock(return_value=False)
  get_apps_db.return_value = apps_db

  app = flask.Flask(__name__)
  app.config.update(REQUEST_METHOD='GET', SERVER_NAME='localhost', SERVER_PORT='5000', SECRET_KEY='a random string', WTF_CSRF_SECRET_KEY='a random string')
  app.config['wsgi.url_scheme'] = 'http'
  app.app_context().push()
  request_context = app.request_context(app.config)
  request_context.request.environ['wsgi.errors'] = None
  request_context.push()

  app = {'name': 'name', 'env': 'env', 'role': 'role'}
  pre_insert_app([app])

  assert app['modules'] == []

  modules = [{'name': 'test', 'git_repo': 'test', 'path': '/var/www', 'scope': 'code'}]
  app = {'name': 'name', 'env': 'env', 'role': 'role', 'modules': modules}
  pre_insert_app([app])

  assert app['modules'][0]['initialized'] == False