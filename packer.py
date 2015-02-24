from uuid import uuid4
from sh import packer, git
import sh
import logging
import yaml
import json
import os
import time
import re

PACKER_JSON_PATH="/tmp/packer/"
SALT_LOCAL_TREE="/tmp/salt/"

class Builder:
    def __init__(self, packer_config):
        self.packer_config = json.loads(packer_config)
        self.unique = str(uuid4())
        if not os.path.exists(PACKER_JSON_PATH):
            os.makedirs(PACKER_JSON_PATH)
        if not os.path.exists(SALT_LOCAL_TREE):
            os.makedirs(SALT_LOCAL_TREE)
        os.makedirs(SALT_LOCAL_TREE + self.unique)
        logging.debug("Getting Salt Morea Formulas")
        git.clone(["https://apestel:***REMOVED***@bitbucket.org/morea/morea-salt-formulas.git", SALT_LOCAL_TREE + self.unique + '/'])

    def _build_salt_top(self):
        self.salt_path = SALT_LOCAL_TREE + self.unique + '/salt'
        self.salt_top_path = self.salt_path + '/' + 'top.sls'
        stream = file(self.salt_top_path, 'w')
        logging.debug("Writing Salt Top state to: {0}".format(self.salt_top_path))
        data = {'*': {'base': ["common","ghost"]}}
        yaml.dump(data, stream, default_flow_style=False)

    def _build_packer_json(self):
        packer_json = {}
        builders = [{
            'type': 'amazon-ebs',
            'region': self.packer_config['region'],
            'ami_name': self.packer_config['ami_name'],
            'source_ami': self.packer_config['source_ami'],
            'instance_type': self.packer_config['instance_type'],
            'ssh_username': self.packer_config['ssh_username'],
            'vpc_id': self.packer_config['vpc_id'],
            'subnet_id': self.packer_config['subnet_id'],
            'associate_public_ip_address': self.packer_config['associate_public_ip_address']
            }]
        provisioners = [{
            'type': 'salt-masterless',
            'local_state_tree': self.salt_path,
            'local_pillar_roots': SALT_LOCAL_TREE + self.unique + '/pillar',
            'skip_bootstrap': True
            }]
        packer_json['builders'] = builders
        packer_json['provisioners'] = provisioners
        self.packer_file_path = PACKER_JSON_PATH + self.unique + ".json" 
        stream = file(self.packer_file_path, 'w')
        logging.debug("Writing Packer definition to: {0}", self.packer_file_path)
        json.dump(packer_json, stream, sort_keys=True, indent=4, separators=(',', ': '))

    def build_image(self):
        self._build_salt_top()
        self._build_packer_json()
        try:
            result = packer.build(self.packer_file_path)
            ami = re.findall('ami-[a-z0-9]*$', result.rstrip())[0]
        except sh.ErrorReturnCode, e:
            print "---- ERROR ----\n" + e.stdout
        print ami

json_datas = {
    'region': 'eu-west-1',
    'ami_name': 'cegos.apache-php.frontend.generated-ami.'+time.strftime("%Y%m%d-%H%M%S"),
    'source_ami': 'ami-cd36b0ba',
    'instance_type': 't2.micro',
    'ssh_username': 'admin',
    'vpc_id': 'vpc-09bb696c',
    'subnet_id': 'subnet-79850e1c',
    'associate_public_ip_address': '1'
}
datas = json.dumps(json_datas, sort_keys=True, indent=4, separators=(',', ': '))

if __name__ == "__main__":
    builder = Builder(packer_config=datas)
    builder.build_image()
