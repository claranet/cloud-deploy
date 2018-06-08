import re

from ghost_data import get_app


class WebhookParser(object):
    """
    Abstract class for webhook parsers with predefined methods.
    """

    def __init__(self, request):
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

    def validate_repo_url(self, app_id, module_name):
        """
        Check one of repo urls matches configuration repo url.
        """
        try:
            app = get_app(app_id)
            for module in app['modules']:
                if (module['name'] == module_name and
                        module['git_repo'] in self.get_repo_urls()):
                    return True

            return False
        except:
            return False

    def validate_event(self, events):
        """
        Check event matches configuration events list.
        """
        return self.get_event() in events

    def validate_revision(self, revision_regex):
        """
        Check revision matches configuration revision regex.
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
        if not self.validate_repo_url(conf['app_id'], conf.get('module', None)):
            return False, 'invalid repo url'

        return True, ''
