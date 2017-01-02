import sh
from sh import git
from subprocess32 import Popen, PIPE
import yaml
import json
import os

from ghost_log import log
from libs.git_helper import git_wait_lock, git_remap_submodule

PACKER_JSON_PATH="/tmp/packer/"
PACKER_LOGDIR="/var/log/ghost/packer"
SALT_LOCAL_TREE="/tmp/salt/"
SALT_LOCAL_MIRROR="/ghost/.mirrors/salt-zabbix-mirror/"
SALT_FORMULAS_REPO="git@bitbucket.org:morea/morea-salt-formulas.git"
ZABBIX_REPO="git@bitbucket.org:morea/zabbix.git"

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
        if not os.path.exists(SALT_LOCAL_TREE):
            os.makedirs(SALT_LOCAL_TREE)
        os.makedirs(SALT_LOCAL_TREE + self.unique)

        #Use the configured git repository, if any
        salt_formulas_repo = config.get('salt_formulas_repo', SALT_FORMULAS_REPO)
        zabbix_repo = config.get('zabbix_repo', ZABBIX_REPO)
        log("Getting Salt Formulas from {r}".format(r=salt_formulas_repo), self._log_file)
        try:
            output=git("ls-remote", "--exit-code", salt_formulas_repo, config.get('salt_formulas_branch', 'master')).strip()
            log("salt_formulas_repo checked successfuly with output: " + output, self._log_file)
        except sh.ErrorReturnCode, e:
            log("Invalid salt formulas repos. Please check your yaml 'config.yml' file", self._log_file)
            raise

        #Creates the SALT local mirror
        if not os.path.exists(SALT_LOCAL_MIRROR):
            log("Creating local mirror [{r}] for the first time".format(r=SALT_LOCAL_MIRROR), self._log_file)
            os.makedirs(SALT_LOCAL_MIRROR)
            os.chdir(SALT_LOCAL_MIRROR)
            git.init(['--bare'])
            git.remote(['add', 'salt', salt_formulas_repo])
            git.remote(['add', 'zabbix', zabbix_repo])

        log("Fetching local mirror [{r}] remotes".format(r=SALT_LOCAL_MIRROR), self._log_file)
        os.chdir(SALT_LOCAL_MIRROR)

        git_wait_lock(SALT_LOCAL_MIRROR, self._log_file)

        git.fetch(['--all'])

        log("Cloning [{r}] repo with local mirror reference".format(r=salt_formulas_repo), self._log_file)
        git.clone(['--reference', SALT_LOCAL_MIRROR, salt_formulas_repo, '-b', config.get('salt_formulas_branch', 'master'), '--single-branch', SALT_LOCAL_TREE + self.unique + '/'])
        if config.get('salt_formulas_branch'):
            os.chdir(SALT_LOCAL_TREE + self.unique)
            git_remap_submodule(SALT_LOCAL_TREE + self.unique, zabbix_repo, SALT_LOCAL_MIRROR, self._log_file)
            log("Submodule init and update", self._log_file)
            git.submodule('init')
            git.submodule('update')

    def _build_salt_top(self, params):
        self.salt_path = SALT_LOCAL_TREE + self.unique + '/salt'
        self.salt_top_path = self.salt_path + '/top.sls'
        stream = file(self.salt_top_path, 'w')
        log("Writing Salt Top state to: {0}".format(self.salt_top_path), self._log_file)
        #The common sls file is optional
        if os.path.exists(self.salt_path + '/common'):
            data = {'base': {'*': ['common'] + params }}
        else:
            data = {'base': {'*': params }}
        log('state: top.sls: {0}'.format(data), self._log_file)
        yaml.dump(data, stream, default_flow_style=False)

    def _build_salt_pillar(self, features):
        self.salt_pillar_path = SALT_LOCAL_TREE + self.unique + '/pillar'
        self.salt_pillar_top_path = self.salt_pillar_path + '/top.sls'
        self.salt_pillar_features_path = self.salt_pillar_path + '/features.sls'
        #Creating top.sls to call features.sls
        stream_top = file(self.salt_pillar_top_path, 'w')
        data_top = {'base': {'*': ['features']}}
        log('pillar: top.sls: {0}'.format(data_top), self._log_file)
        yaml.dump(data_top, stream_top, default_flow_style=False)
        #Creating features.sls file based on ghost app features
        stream_features = file(self.salt_pillar_features_path, 'w')
        log('pillar: features.sls: {0}'.format(features), self._log_file)
        yaml.dump(features, stream_features, default_flow_style=False)

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
        provisioners = [
        {
            'type': 'shell',
            'environment_vars': formatted_env_vars,
            'script': hooks['pre_buildimage']
        },
        {
            'type': 'salt-masterless',
            'local_state_tree': self.salt_path,
            'local_pillar_roots': SALT_LOCAL_TREE + self.unique + '/pillar',
            'skip_bootstrap': self.packer_config['skip_salt_bootstrap'],
        },
        {
            'type': 'shell',
            'environment_vars': formatted_env_vars,
            'script': hooks['post_buildimage']
        },
        {
            'type': 'shell',
            'inline': ["sudo rm -rf /srv/salt || echo 'salt: no cleanup salt'", "sudo rm -rf /srv/pillar || echo 'salt: no cleanup pillar'"]
        }]

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

    def build_image(self, salt_params, features, hooks):
        self._build_salt_top(salt_params)
        self._build_salt_pillar(features)
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
