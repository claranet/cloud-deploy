import os
import json

VAR_FILE = "/tmp/packer_var.json"

class PackerVar:
    def __init__(self):
        self._var_file = VAR_FILE

    def create_vars(var_list):
        with file(self._var_file, 'w') as var_file:
            json.dump(var_list, var_file, indent=4, separators=(',', ': '))

    def delete_vars():
        os.remove(self._var_file)

    def get_var_file():
        return(self._var_file)

