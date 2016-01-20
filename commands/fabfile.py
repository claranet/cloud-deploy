from StringIO import StringIO
from fabric.api import sudo, task, env, put, settings
import yaml
import os

from ghost_tools import render_stage2

env.user = 'admin'
env.connection_attempts = 10
env.timeout = 30

@task
def deploy(bucket_s3, bucket_region, module):
    #TODO: remove no longer used bucket_s3 param
    with settings(warn_only=True):
        sudo('rm -rvf /tmp/stage2')
        with open(os.path.dirname(os.path.realpath(__file__)) + '/../config.yml', 'r') as conf_file:
            config = yaml.load(conf_file)
        put(StringIO(render_stage2(config, bucket_region)), '/tmp/stage2')
        sudo('chmod +x /tmp/stage2')
        sudo('/tmp/stage2 %s' % module)
