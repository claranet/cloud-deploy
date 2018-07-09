import os

from subprocess32 import Popen, PIPE

from ghost_log import log
from ghost_tools import boolify

PACKER_LOGDIR="/var/log/ghost/packer"


class Packer:
    def __init__(self, credentials, log_file):
        self._log_file = log_file
        self._aws_credentials = credentials
        self._assumed_role = boolify(self._aws_credentials.get('aws_access_key', False))

    def _run_packer_cmd(self, cmd):
        """
        Triggers the Packer command line

        :param cmd: command arguments
        :return: The result of the command execution
        """
        result = ""
        packer_env = os.environ.copy()
        if not os.path.isdir(PACKER_LOGDIR):
            os.makedirs(PACKER_LOGDIR)
        packer_env['TMPDIR'] = PACKER_LOGDIR
        if self._assumed_role:
            packer_env['AWS_ACCESS_KEY_ID'] = self._aws_credentials['aws_access_key']
            packer_env['AWS_SECRET_ACCESS_KEY'] = self._aws_credentials['aws_secret_key']
            packer_env['AWS_SESSION_TOKEN'] = self._aws_credentials['token']
            packer_env['AWS_SECURITY_TOKEN'] = self._aws_credentials['token']
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
                    if msg_type == "ui" and len(out_tab) > 4:
                        log("{0}".format(out_tab[4]), self._log_file)
                    elif msg_type == "artifact":
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
        # Packer returns a line formatted as {aws-region}:{ami-id}
        ami_id = result.split(':')[1] if ret_code == 0 else None
        return ami_id or "ERROR"
