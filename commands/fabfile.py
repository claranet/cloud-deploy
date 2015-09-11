import os, tempfile
from fabric.api import sudo, task, env, put, settings
from jinja2 import Environment, FileSystemLoader
env.user = 'admin'

@task
def deploy(bucket_s3, module):
    with settings(warn_only=True):
        bootstrap, bootstrap_path = tempfile.mkstemp()
        jinja_env = Environment(loader=FileSystemLoader('%s/../scripts' % os.path.dirname(os.path.realpath(__file__))))
        template = jinja_env.get_template('stage2')
        #template.render(bucket_s3=bucket_s3).stream(name='bootstrap').dump(bootstrap_path)
        template.stream(bucket_s3=bucket_s3).dump(bootstrap_path)
        sudo('rm -rvf /tmp/stage2')
        put('%s' % bootstrap_path, '/tmp/stage2')
        os.remove(bootstrap_path)
        sudo('chmod +x /tmp/stage2')
        sudo('/tmp/stage2 %s' % module)