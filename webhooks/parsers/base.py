import re

from ghost_data import get_app
from mock import MagicMock


class WebhookParser(object):
    """
    Abstract class for webhook parsers with predefined methods.
    """

    def __init__(self, request):
        if request:
            self._headers = request.headers
            self._payload = request.get_json()
            self._payload_text = request.get_data(as_text=True)
        self._data = {}

    def get_repo_urls(self):
        """
        Get all urls related to source repository: base / https / ssh.
        """
        pass

    def get_event(self):
        """
        Get webhook event.
        """
        pass

    def get_revision(self):
        """
        Get webhook revision.
        """
        pass

    def get_secret_token(self):
        """
        Get webhook secret token.
        """
        pass

    def get_data(self):
        """
        Get webhook data. Parse webhook request if _data isn't defined.
        """
        if not self._data:
            self.parse_request()

        return self._data

    def parse_request(self):
        """
        Parse request and store job's configuration in job_conf.
        """
        self._data['event'] = self.get_event()
        self._data['repo_urls'] = self.get_repo_urls()
        self._data['rev'] = self.get_revision()
        self._data['secret_token'] = self.get_secret_token()

    def validate_repo_url(self, app, module_name):
        """
        Check one of repo urls matches configuration repo url.

        >>> app = {'name': 'name', 'env': 'env', 'role': 'role', 'modules': [{'name': 'wordpress', 'git_repo': 'git@github.com:test/test.git', 'scope': 'code', 'path': '/var/www'}]}
        >>> urls = ['git@github.com:test/test.git']
        >>> test_parser = WebhookParser(None)
        >>> test_parser.get_repo_urls = MagicMock(return_value=urls)

        >>> test_parser.validate_repo_url(app, 'wordpress')
        True

        >>> test_parser.validate_repo_url(app, 'unknown')
        False

        >>> app['modules'][0]['git_repo'] = 'https://github.com/test/test.git'
        >>> test_parser.validate_repo_url(app, 'wordpress')
        False
        """
        for module in app.get('modules', []):
            if (module['name'] == module_name and
                    module['git_repo'] in self.get_repo_urls()):
                return True

        return False

    def validate_event(self, events):
        """
        Check event matches configuration events list.

        >>> test_parser = WebhookParser(None)
        >>> test_parser.get_event = MagicMock(return_value='push')

        >>> test_parser.validate_event('push')
        True

        >>> test_parser.validate_event('tag')
        False
        """
        return self.get_event() in events

    def validate_revision(self, revision_regex):
        """
        Check revision matches configuration revision regex.

        >>> test_parser = WebhookParser(None)
        >>> test_parser.get_revision = MagicMock(return_value='testing_env')

        >>> test_parser.validate_revision('test*') is not None
        True

        >>> test_parser.validate_revision('prod*') is not None
        False
        """
        return re.search(revision_regex, self.get_revision())

    def validate_secret(self, secret_token):
        """
        Check VCS secret token matches configuration secret. Returns True if no secret defined.
        """
        pass

    def validate_request(self, conf):
        """
        Check the webhook's request matches webhook's Cloud Deploy configuration.
        """
        # Get app data, useful for some checks
        app = get_app(conf.get('app_id'))

        # Check secret is valid if there's one
        if not self.validate_secret(conf.get('secret_token', None)):
            return False, 'invalid secret'

        # Check event is valid
        if not self.validate_event(conf.get('events', None)):
            return False, 'invalid event'

        # Check rev is valid
        if not self.validate_revision(conf.get('rev', None)):
            return False, 'invalid revision'

        # Check repo url is valid
        if not self.validate_repo_url(app, conf.get('module', None)):
            return False, 'invalid repo url'

        return True, ''
