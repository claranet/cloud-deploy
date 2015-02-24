from ..packer import Packer
from commands.tools import log

class BuildImage():
    _app = None
    _job = None
    _log_file = -1

    def __init__(self, worker):
        self._app = worker.app
        self._job = worker.job
        self._db = worker._db
        self._log_file = worker.log_file
        self._ami_name = '{0}.{1}'.format(self._app['name'], time.strftime("%Y%m%d-%H%M%S")

    def _format_packer_from_app(self):
        datas = {
            'region': self._app['region'],
            'ami_name': self._ami_name,
            'source_ami': self._app['build_infos']['source_ami'],
            'instance_type': 't2.micro',
            'ssh_username': self._app['build_infos']['ssh_username'],
            'vpc_id': self._app['vpc_id'],
            'subnet_id': self._app['subnet_id'],
            'associate_public_ip_address': '1'
        }
        return json.dumps(datas, sort_keys=True, indent=4, separators=(',', ': '))

    def _update_app_ami(self, ami_id):
    self._db.apps.update({'_id': self._app['_id']},{'$set': {'ami': ami_id, 'ami_name': self.ami_name}})

    def execute(self):
    json_packer = self._format_packer_from_app()
        log("Generating a new AMI", self._log_file)
        log(json_packer, self._log_file)
        ami_id = Packer(json_packer)
        log("Update app in MongoDB to update AMI: {0}".format(ami_id), self._log_file)
        self._update_app_ami(ami_id)

