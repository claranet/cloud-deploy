import sh
from subprocess32 import Popen, PIPE
import json
import os

from ghost_tools import GCallException, get_provisioners_config
from ghost_log import log


PACKER_JSON_PATH="/tmp/packer/"
PACKER_LOGDIR="/var/log/ghost/packer"


class Packer:
    def __init__(self, credentials, config, log_file, job_id):
        self._log_file = log_file
        self.packer_config = json.loads(credentials)
        self.packer_json_path = PACKER_JSON_PATH
        if self.packer_config['credentials']['aws_access_key']:
            self._assumed_role = True
        else:
            self._assumed_role = False

        self.unique = str(job_id)
        if not os.path.exists(PACKER_JSON_PATH):
            os.makedirs(PACKER_JSON_PATH)

    def _run_packer_cmd(self, cmd):
        result = ""
        packer_env = os.environ.copy()
        if not os.path.isdir(PACKER_LOGDIR):
            os.makedirs(PACKER_LOGDIR)
        packer_env['TMPDIR'] = PACKER_LOGDIR
        if self._assumed_role:
            packer_env['AWS_ACCESS_KEY_ID'] = self.packer_config['credentials']['aws_access_key']
            packer_env['AWS_SECRET_ACCESS_KEY'] = self.packer_config['credentials']['aws_secret_key']
            packer_env['AWS_SESSION_TOKEN'] = self.packer_config['credentials']['token']
            packer_env['AWS_SECURITY_TOKEN'] = self.packer_config['credentials']['token']
        process = Popen(cmd, stdout=PIPE, env=packer_env)
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

    def build_image(self, packer_file_path):

        ret_code, result = self._run_packer_cmd(
                                        [
                                            'packer',
                                            'build',
                                            '-machine-readable',
                                            packer_file_path
                                        ]
                                    )
        if (ret_code == 0):
            ami = result.split(':')[1]
        else:
            ami = "ERROR"
        return ami
