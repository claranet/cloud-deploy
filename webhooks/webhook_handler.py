from eve.methods.post import post_internal

from ghost_data import get_webhook
from parsers.bitbucket import BitbucketWebhookParser
from parsers.github import GithubWebhookParser
from parsers.gitlab import GitlabWebhookParser


class WebhookHandler:
    def __init__(self, webhook_id, request):
        self._request = request
        self._headers = request.headers
        self._parser = None
        self._conf = {}
        self._webhook_id = webhook_id

        if 'X-GitHub-Event' in self._headers:
            self._parser = GithubWebhookParser(self._request)
        elif 'X-Event-Key' in self._headers:
            self._parser = BitbucketWebhookParser(self._request)
        elif 'X-Gitlab-Event' in self._headers:
            self._parser = GitlabWebhookParser(self._request)

    def load_conf(self):
        self._conf = get_webhook(self._webhook_id)

    def get_conf(self):
        if not self._conf:
            self.load_conf()

        return self._conf

    def get_attribute(self, key):
        return self.get_conf().get(key, None)

    def parse_request(self):
        self._parser.parse_request()

    def validate_request(self):
        return self._parser.validate_request(self.get_conf())

    def create_job_configuration(self):
        job_conf = {
            'app_id': self.get_attribute('app_id'),
        }
        if 'safe_deployment_strategy' in self.get_conf():
            job_conf['safe_deployment_strategy'] = self.get_attribute('safe_deployment_strategy')
        if 'module' in self.get_conf():
            job_conf['modules'] = [{
                'name': self.get_attribute('module'),
                'rev': str(self._parser.get_revision())
            }]
        if 'instance_type' in self.get_conf():
            job_conf['instance_type'] = self.get_attribute('instance_type')

        return job_conf

    def start_jobs(self):
        job_conf = self.create_job_configuration()
        results = ''
        errors = False

        for command in set(self.get_attribute('commands')):
            job_conf['command'] = command
            job, _, _, rc, _ = post_internal('jobs', job_conf)
            if rc >= 400:
                results += '- failed to start job {command}: {err}\n'.format(command=command, err=str(job))
                errors = True
            else:
                results += '- job {command} has been created: {job}\n'.format(command=command, job=str(job))

        return results, errors
