from StringIO import StringIO
from fabric.api import show, sudo, task, env, put, settings
import yaml
import os

from commands.ghost_tools import render_stage2

with open(os.path.dirname(os.path.realpath(__file__)) + '/../config.yml', 'r') as conf_file:
    config = yaml.load(conf_file)

env.abort_on_prompts = True
env.use_ssh_config = config.get('use_ssh_config', False)

env.connection_attempts = 10
env.timeout = 30

@task
def deploy(module, ssh_username, key_filename, bucket_region, log_file):
    with settings(show('debug'), warn_only=True, user=ssh_username, key_filename=key_filename):
        sudo('rm -rvf /tmp/stage2', stdout=log_file)
        put(StringIO(render_stage2(config, bucket_region)), '/tmp/stage2')
        sudo('chmod +x /tmp/stage2', stdout=log_file)
        sudo('/tmp/stage2 %s' % module, stdout=log_file)
