from uuid import uuid4
from sh import packer, git
import logging
from yaml

PACKER_JSON_PATH="/tmp/packer/"
SALT_LOCAL_TREE="/tmp/salt/"

class Builder:
    def __init__(self):
        self.unique = uuid4()
        if not os.path.exists(PACKER_JSON_PATH):
            os.makedirs(PACKER_JSON_PATH)
        if not os.path.exists(SALT_LOCAL_TREE):
            os.makedirs(SALT_LOCAL_TREE)
        os.makedirs(SALT_LOCAL_TREE + unique)
        logging.debug("Getting Salt Morea Formulas")
        git.clone(["git@bitbucket.org:morea/morea-salt-formulas.git", SALT_LOCAL_TREE + unique + '/'])

    def _build_salt_top(self):
        self.salt_path = SALT_LOCAL_TREE + self.unique
        salt_top_path = salt_path + '/' + 'top.sls'
        stream = file(salt_top_path, 'w')
        logging.debug("Writing Salt Top state to: {0}".format(salt_top_path))
        yaml.dump(salt_top, stream)

    def _build_packer_json(self):
        packer_json = {}
        builders = [{
            'type': 'amazon-ebs',
            'region': 'eu-west-1'
            }]
        provisioners = [{
            'type': 'salt-masterless',
            'local_state_tree': self.salt_path,
            'skip_bootstrap': True
            }]
        packer_json['builders'] = builders
        packer_json['provisioners'] = provisioners
        self.packer_file_path = PACKER_JSON_PATH + self.unique + ".json" 
        stream = file(packer_file_path, 'w')
        logging.debug("Writing Packer definition to: {0}", packer_file_path)
        json.dump(packer_json, stream, sort_keys=True, indent=4, separators=(',', ': '))

    def build_image(self):
        _build_salt_top()
        _build_packer_json()
        packer.build(self.packer_file_path)

if __name__ == "__main__":
    builder = Builder()
    builder.build_image()
