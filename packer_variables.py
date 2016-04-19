import os
import json

VAR_FILE = "/tmp/packer_var.json"

class PackerVar:
    def __init__(self):
        self._var_file = VAR_FILE

    def create_vars(self, var_list):
        with file(self._var_file, 'w') as var_file:
            json.dump(var_list, var_file, indent=4, separators=(',', ': '))

    def delete_vars(self):
        os.remove(self._var_file)

    def get_var_file(self):
        return(self._var_file)

