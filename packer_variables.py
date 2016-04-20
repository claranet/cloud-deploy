import os
import json
from uuid import uuid4

PACKER_VAR_PATH = "/tmp/packer/"

class PackerVar:
    def __init__(self):
        self.unique = str(uuid4())
        if not os.path.exists(PACKER_VAR_PATH):
            os.makedirs(PACKER_VAR_PATH)
        self._var_file = PACKER_VAR_PATH + self.unique + ".json"

    def create_vars(self, var_list):
        with file(self._var_file, 'w') as var_file:
            json.dump(var_list, var_file, indent=4, separators=(',', ': '))

    def delete_vars(self):
        if os.path.exists(self._var_file):
            os.remove(self._var_file)

    def get_var_file(self):
        return(self._var_file)

