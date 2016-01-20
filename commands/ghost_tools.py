import os

from jinja2 import Environment, FileSystemLoader

from boto import s3

def render_stage2(config, s3_region):
    """
    Renders the stage2 script that is the second step of EC2 instance bootstrapping through userdata (stage1).

    The 'config' dict should contain the following parameters:
    * 'bucket_s3': name of the Ghost S3 bucket (required)
    * 'ghost_root_path': path to the root of the Ghost installation (required)
    * 'max_deploy_history': maximum number of deployments to preserve after a deployment (optional).

    If 'max_deploy_history' is not defined in the 'config' dict, the render_stage2() function uses 3 as the default value:

    >>> config = {'bucket_s3': 'my-s3-bucket', 'ghost_root_path': '.'}
    >>> stage2 = render_stage2(config, '')
    >>> stage2[stage2.find('S3_BUCKET'):stage2.find('\\n', stage2.find('S3_BUCKET')+1)]
    u'S3_BUCKET=my-s3-bucket'
    >>> stage2[stage2.find('MAX_DEPLOY_HISTORY'):stage2.find('\\n', stage2.find('MAX_DEPLOY_HISTORY')+1)]
    u'MAX_DEPLOY_HISTORY="3"'

    This can be overridden by defining the 'max_deploy_history' configuration setting:

    >>> config = {'bucket_s3': 'my-s3-bucket', 'ghost_root_path': '.', 'max_deploy_history': 1}
    >>> stage2 = render_stage2(config, '')
    >>> stage2[stage2.find('S3_BUCKET'):stage2.find('\\n', stage2.find('S3_BUCKET')+1)]
    u'S3_BUCKET=my-s3-bucket'
    >>> stage2[stage2.find('MAX_DEPLOY_HISTORY'):stage2.find('\\n', stage2.find('MAX_DEPLOY_HISTORY')+1)]
    u'MAX_DEPLOY_HISTORY="1"'
    """
    bucket_s3 = config['bucket_s3']
    ghost_root_path = config['ghost_root_path']
    max_deploy_history = config.get('max_deploy_history', 3)

    jinja_templates_path='%s/scripts' % ghost_root_path
    if(os.path.exists('%s/stage2' % jinja_templates_path)):
        loader=FileSystemLoader(jinja_templates_path)
        jinja_env = Environment(loader=loader)
        template = jinja_env.get_template('stage2')
        return template.render(bucket_s3=bucket_s3, max_deploy_history=max_deploy_history, bucket_region=s3_region)
    return None

def refresh_stage2(region, config):
    """
    Will update the second phase of bootstrap script on S3
    """
    conn = s3.connect_to_region(region)
    bucket_s3 = config['bucket_s3']
    bucket = conn.get_bucket(bucket_s3)
    stage2 = render_stage2(config, region)
    if stage2 is not None:
        key = bucket.new_key("/ghost/stage2")
        key.set_contents_from_string(stage2)
        key.close()
    else:
        bucket.delete_key("/ghost/stage2")
