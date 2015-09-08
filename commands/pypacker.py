from uuid import uuid4
from sh import git
from subprocess32 import Popen, PIPE
from commands.tools import log
import logging
import yaml
import json
import os

PACKER_JSON_PATH="/tmp/packer/"
SALT_LOCAL_TREE="/tmp/salt/"

logging.basicConfig(filename="/tmp/packer.log")

class Packer:
    def __init__(self, packer_config, config, log_file):
        print("Packer __init__ start")
        self._log_file = log_file
        self.packer_config = json.loads(packer_config)
        self.unique = str(uuid4())
        if not os.path.exists(PACKER_JSON_PATH):
            os.makedirs(PACKER_JSON_PATH)
        if not os.path.exists(SALT_LOCAL_TREE):
            os.makedirs(SALT_LOCAL_TREE)
        os.makedirs(SALT_LOCAL_TREE + self.unique)
        logging.debug("Getting Salt Morea Formulas")
        git.clone(["git@bitbucket.org:morea/morea-salt-formulas.git", SALT_LOCAL_TREE + self.unique + '/'],'--recursive')
        if config.get('salt_formulas_branch'):
            os.chdir(SALT_LOCAL_TREE + self.unique)
            git.checkout(config['salt_formulas_branch'])

    def _build_salt_top(self, params):
        self.salt_path = SALT_LOCAL_TREE + self.unique + '/salt'
        self.salt_top_path = self.salt_path + '/top.sls'
        stream = file(self.salt_top_path, 'w')
        logging.debug("Writing Salt Top state to: {0}".format(self.salt_top_path))
        data = {'base': {'*': ['common']}}
        data['base']['*'] = params
        print('state: top.sls: {0}'.format(data))
        yaml.dump(data, stream, default_flow_style=False)

    def _build_salt_pillar(self, features):
        self.salt_pillar_path = SALT_LOCAL_TREE + self.unique + '/pillar'
        self.salt_pillar_top_path = self.salt_pillar_path + '/top.sls'
        self.salt_pillar_features_path = self.salt_pillar_path + '/features.sls'
        #Creating top.sls to call features.sls
        stream_top = file(self.salt_pillar_top_path, 'w')
        data_top = {'base': {'*': ['features']}}
        print('pillar: top.sls: {0}'.format(data_top))
        yaml.dump(data_top, stream_top, default_flow_style=False)
        #Creating features.sls file based on ghost app features
        stream_features = file(self.salt_pillar_features_path, 'w')
        print('pillar: features.sls: {0}'.format(features))
        yaml.dump(features, stream_features, default_flow_style=False)

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
            'associate_public_ip_address': self.packer_config['associate_public_ip_address'],
            'ami_block_device_mappings': self.packer_config['ami_block_device_mappings']
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
        print('packer file path: {0}'.format(self.packer_file_path))
        stream = file(self.packer_file_path, 'w')
        logging.debug("Writing Packer definition to: {0}", self.packer_file_path)
        json.dump(packer_json, stream, sort_keys=True, indent=4, separators=(',', ': '))

    def _run_packer_cmd(self, cmd):
        result = ""
        process = Popen(cmd, stdout=PIPE)
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                out_tab = output.strip().split(',')
                if len(out_tab) > 3:
                    ts = out_tab[0]
                    target = out_tab[1]
                    msg_type = out_tab[2]
                    data = out_tab[3]
                    if (msg_type == "ui" and len(out_tab) > 4):
                        log("{0}".format(out_tab[4]), self._log_file)
                    elif (msg_type == "artifact"):
                        if len(out_tab) > 4 and out_tab[4] == "id":
                            result = out_tab[5]
                            log("AMI: {0}".format(result), self._log_file)
                    else:
                        log("{0}: {1}".format(msg_type, data), self._log_file)
        rc = process.poll()
        return rc, result

    def build_image(self, salt_params, features):
        self._build_salt_top(salt_params)
        self._build_salt_pillar(features)
        self._build_packer_json()
        if not os.path.isdir('/tmp/root'):
            os.makedirs('/tmp/root')
        ret_code, result = self._run_packer_cmd(['packer', 'build', '-machine-readable', self.packer_file_path])
        if (ret_code == 0):
            ami = result.split(':')[1]
        else:
            ami = "ERROR"
        return ami
