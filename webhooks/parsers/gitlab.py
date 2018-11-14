from base import WebhookParser


class GitlabWebhookParser(WebhookParser):
    def get_repo_urls(self):
        event = self.get_event()
        urls = []
        url_types = ['url', 'git_http_url', 'git_ssh_url']

        if event in ['push', 'tag']:
            return [self._payload['repository'][url_type] for url_type in url_types]
        elif event == 'merge':
            return [self._payload['object_attributes']['target'][url_type] for url_type in url_types]

    def get_event(self):
        event = self._headers['x-gitlab-event']

        if event == 'Push Hook':
            return 'push'
        elif event == 'Tag Push Hook':
            return 'tag'
        elif event == 'Merge Request Hook':
            return 'merge'

        return event

    def get_revision(self):
        event = self.get_event()

        if event in ['push', 'tag']:
            return self._payload['ref']
        elif event == 'merge':
            return self._payload['object_attributes']['target_branch']

        return None

    def get_secret_token(self):
        return self._headers.get('X-Gitlab-Token', None)

    def validate_secret(self, secret_token):
        return not secret_token or secret_token == self.get_secret_token()
