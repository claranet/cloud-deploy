import hmac
import re
from hashlib import sha1

from base import WebhookParser


class GithubWebhookParser(WebhookParser):
    def get_repo_urls(self):
        url_types = ['url', 'git_url', 'clone_url', 'ssh_url']
        return [self._payload['repository'][url_type] for url_type in url_types]

    def get_event(self):
        event = self._headers['x-github-event']

        if event == 'push':
            return 'push'
        elif event == 'create':
            if self._payload['ref_type'] == 'tag':
                return 'tag'
        elif event == 'pull_request':
            if self._payload['action'] == 'closed' and self._payload['pull_request']['merged']:
                return 'merge'

        return event

    def get_revision(self):
        event = self.get_event()

        if event in ['push', 'tag']:
            return re.sub('^refs\/(heads|tags)\/', '', self._payload['ref'])
        elif event == 'merge':
            return self._payload['pull_request']['base']['ref']

        return None

    def get_secret_token(self):
        return self._headers.get('X-Hub-Signature', None)

    def validate_secret(self, secret_token):
        if not secret_token:
            return True

        token = "sha1=" + hmac.new(str(secret_token),
                                   str(self._payload_text),
                                   sha1).hexdigest()

        return token == self.get_secret_token()
