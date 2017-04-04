import sh
from subprocess32 import Popen, PIPE
import json
import os

from ghost_log import log
from libs.provisioner_salt import FeaturesProvisionerSalt

PACKER_JSON_PATH="/tmp/packer/"
PACKER_LOGDIR="/var/log/ghost/packer"

class Packer:
    def __init__(self, packer_config, config, log_file, job_id):
        self._log_file = log_file
        self.packer_config = json.loads(packer_config)
        if self.packer_config['credentials']['aws_access_key']:
            self._assumed_role = True
        else:
            self._assumed_role = False

        self.unique = str(job_id)
        if not os.path.exists(PACKER_JSON_PATH):
            os.makedirs(PACKER_JSON_PATH)

        provisioners_config = config.get('features_provisioners', {
            'salt': {
                'git_repo': config.get('salt_formulas_repo', 'git@bitbucket.org:morea/morea-salt-formulas.git'),
                'git_revision': config.get('salt_formulas_branch', 'master'),
            }
        })

        self.provisioners = []
        for key, provisioner_config in provisioners_config.iteritems():
            if key == 'salt':
                self.provisioners.append(FeaturesProvisionerSalt(self._log_file, self.unique, provisioner_config, config))

    def _build_packer_json(self, hooks):
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
            'ami_block_device_mappings': self.packer_config['ami_block_device_mappings'],
            'ssh_pty': 'true',
            'iam_instance_profile': self.packer_config['iam_instance_profile'],
            'tags': self.packer_config['tags']
        }]

        formatted_env_vars = self.packer_config['ghost_env_vars'] + ['%s=%s' % (envvar['var_key'], envvar['var_value']) for envvar in self.packer_config['custom_env_vars']]
        provisioners = [{
            'type': 'shell',
            'environment_vars': formatted_env_vars,
            'script': hooks['pre_buildimage']
        }]

        for provisioner in self.provisioners:
            provisioners.append(provisioner.build_packer_provisioner_config(self.packer_config))

        provisioners.append({
            'type': 'shell',
            'environment_vars': formatted_env_vars,
            'script': hooks['post_buildimage']
        })

        for provisioner in self.provisioners:
            provisioners.append(provisioner.build_packer_provisioner_cleanup())

        packer_json['builders'] = builders
        packer_json['provisioners'] = provisioners
        self.packer_file_path = PACKER_JSON_PATH + self.unique + ".json"
        log('packer file path: {0}'.format(self.packer_file_path), self._log_file)
        stream = file(self.packer_file_path, 'w')
        log("Writing Packer definition to: {0}".format(self.packer_file_path), self._log_file)
        json.dump(packer_json, stream, sort_keys=True, indent=4, separators=(',', ': '))

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

    def build_image(self, features_infos, hooks):
        for provisioner in self.provisioners:
            provisioner_params = provisioner.format_provisioner_params(features_infos)
            features = provisioner.format_provisioner_features(features_infos)
            provisioner.build_provisioner_features_files(provisioner_params, features)

        self._build_packer_json(hooks)
        ret_code, result = self._run_packer_cmd(
                                        [
                                            'packer',
                                            'build',
                                            '-machine-readable',
                                            self.packer_file_path
                                        ]
                                    )
        if (ret_code == 0):
            ami = result.split(':')[1]
        else:
            ami = "ERROR"
        return ami
