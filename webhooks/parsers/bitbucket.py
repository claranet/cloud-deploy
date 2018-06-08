from base import WebhookParser


class BitbucketWebhookParser(WebhookParser):
    def get_repo_urls(self):
        urls = [self._payload['repository']['links']['html']['href']]

        if 'full_name' in self._payload['repository']:
            name = self._payload['repository']['full_name']

        if name:
            urls.append('git@bitbucket.org:{name}.git'.format(name=name))
            urls.append('https://bitbucket.org/{name}.git'.format(name=name))

        return urls

    def get_event(self):
        event = self._headers['X-Event-Key']

        if event == 'repo:push':
            event_ = self._payload['push']['changes'][0]['new']['type']
            if event_ == 'branch':
                return 'push'
            elif event_ == 'tag':
                return 'tag'
        elif event == 'pullrequest:fulfilled':
            return 'merge'

        return event

    def get_revision(self):
        event = self.get_event()

        if event in ['push', 'tag']:
            return self._payload['push']['changes'][0]['new']['name']
        elif event == 'merge':
            return self._payload['pullrequest']['destination']['branch']['name']

        return None

    def get_secret_token(self):
        return None

    def validate_secret(self, secret_token):
        return True
