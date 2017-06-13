# -*- coding: utf-8 -*-
from StringIO import StringIO
from fabric.api import show, sudo, task, env, put, settings, output
from fabric.context_managers import shell_env
import yaml
import os

with open(os.path.dirname(os.path.realpath(__file__)) + '/config.yml', 'r') as conf_file:
    config = yaml.load(conf_file)

env.abort_on_prompts = True
env.use_ssh_config = config.get('use_ssh_config', False)

env.connection_attempts = 10
env.timeout = 30

env.skip_bad_hosts = True
env.colorize_errors = True

output.debug = True

@task
def deploy(module, ssh_username, key_filename, stage2, log_file):
    with settings(show('debug'), warn_only=True, user=ssh_username, key_filename=key_filename):
        sudo('rm -rvf /tmp/stage2', stdout=log_file)
        put(StringIO(stage2), '/tmp/stage2')
        sudo('chmod +x /tmp/stage2', stdout=log_file)
        result = sudo('/tmp/stage2 %s' % module['name'], stdout=log_file)
        return result.return_code

@task
def executescript(ssh_username, key_filename, context_path, sudoer_user, jobid, hot_script, log_file, ghost_env):
    with settings(show('debug'), warn_only=True, user=ssh_username, key_filename=key_filename):
        working_dir = '/ghost/%s' % jobid
        sudo('mkdir -p "%s"' % working_dir, stdout=log_file)
        put(StringIO(hot_script), '%s/ghost-execute-script' % working_dir, use_sudo=True)
        sudo('chmod +x %s/ghost-execute-script' % working_dir, stdout=log_file)
        with shell_env(**ghost_env):
            result = sudo('cd "{c}" && {w}/ghost-execute-script'.format(c=context_path, w=working_dir), stdout=log_file, user=sudoer_user)
            return result.return_code
