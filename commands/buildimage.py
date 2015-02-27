import time
import json
from commands.pypacker import Packer
from commands.tools import log

class Buildimage():
    _app = None
    _job = None
    _log_file = -1

    def __init__(self, worker):
        self._app = worker.app
        self._job = worker.job
        self._db = worker._db
        self._worker = worker
        self._log_file = worker.log_file
        self._ami_name = '{0}.{1}'.format(self._app['name'], time.strftime("%Y%m%d-%H%M%S"))

    def _format_packer_from_app(self):
        datas = {
            'region': self._app['region'],
            'ami_name': self._ami_name,
            'source_ami': self._app['build_infos']['source_ami'],
            'instance_type': 't2.micro',
            'ssh_username': self._app['build_infos']['ssh_username'],
            'vpc_id': self._app['vpc_id'],
            'subnet_id': self._app['build_infos']['subnet_id'],
            'associate_public_ip_address': '1'
        }
        return json.dumps(datas, sort_keys=True, indent=4, separators=(',', ': '))

    def _format_salt_top_from_app_features(self):
        top = []
        for i in self._app['features']:
            top.append(i['name'].encode('utf-8'))
        return top

    def _format_salt_pillar_from_app_features(self):
        pillar = {}
        for i in self._app['features']:
            pillar[i['name'].encode('utf-8')] = {}
            pillar[i['name'].encode('utf-8')] = {'version': i['version'].encode('utf-8')}
        return pillar

    def _update_app_ami(self, ami_id):
            self._db.apps.update({'_id': self._app['_id']},{'$set': {'ami': ami_id, 'ami_name': self._ami_name}})
            self._worker.update_status("done")

    def execute(self):
        json_packer = self._format_packer_from_app()
        log("Generating a new AMI", self._log_file)
        log(json_packer, self._log_file)
        pack = Packer(json_packer)
        ami_id = pack.build_image(self._format_salt_top_from_app_features(), self._format_salt_pillar_from_app_features())
        log("Update app in MongoDB to update AMI: {0}".format(ami_id), self._log_file)
        self._update_app_ami(ami_id)

