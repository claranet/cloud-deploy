import flask
import mock
from mock import MagicMock
from run import pre_insert_app
from tests.helpers import create_test_app_context


@mock.patch('run.get_apps_db')
@mock.patch('run.request')
def test_application_pre_insert(request, get_apps_db):
  apps_db = MagicMock()
  apps_db.find_one = MagicMock(return_value=False)
  get_apps_db.return_value = apps_db

  create_test_app_context()

  app = {'name': 'name', 'env': 'env', 'role': 'role'}
  pre_insert_app([app])

  assert app['modules'] == []

  modules = [{'name': 'test', 'git_repo': 'test', 'path': '/var/www', 'scope': 'code'}]
  app = {'name': 'name', 'env': 'env', 'role': 'role', 'modules': modules}
  pre_insert_app([app])

  assert app['modules'] == [{'initialized': False, 'path': '/var/www', 'scope': 'code', 'name': 'test', 'git_repo': 'test'}]
  assert app['environment_infos'] == {'instance_tags': [{'tag_name': 'Name', 'tag_value': 'ec2.env.role.name'}]}