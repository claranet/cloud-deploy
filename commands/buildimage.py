import json
import re
import time
import io
import os

from pypacker import Packer
from ghost_log import log
from ghost_aws import create_launch_config, generate_userdata, check_autoscale_exists, purge_launch_configuration, update_auto_scale
from ghost_tools import get_aws_connection_data, b64decode_utf8
from settings import cloud_connections, DEFAULT_PROVIDER

COMMAND_DESCRIPTION = "Build Image"

class Buildimage():
    _app = None
    _job = None
    _log_file = -1

    def __init__(self, worker):
        self._app = worker.app
        self._job = worker.job
        self._db = worker._db
        self._worker = worker
        self._config = worker._config
        self._log_file = worker.log_file
        self._connection_data = get_aws_connection_data(
                self._app.get('assumed_account_id', ''),
                self._app.get('assumed_role_name', ''),
                self._app.get('assumed_region_name', '')
                )
        self._cloud_connection = cloud_connections.get(self._app.get('provider', DEFAULT_PROVIDER))(
                self._log_file,
                **self._connection_data
                )
        self._ami_name = "ami.{0}.{1}.{2}.{3}.{4}".format(self._app['env'], self._app['region'], self._app['role'], self._app['name'], time.strftime("%Y%m%d-%H%M%S"))

    def _purge_old_images(self):
        conn = self._cloud_connection.get_connection(self._app['region'], ["ec2"])
        retention = self._config.get('ami_retention', 5)
        filtered_images = []
        images = conn.get_all_images(owners="self")

        ami_name_format = "ami.{0}.{1}.{2}.{3}".format(self._app['env'], self._app['region'], self._app['role'], self._app['name'])

        for image in images:
            #log(image.name, self._log_file)
            if ami_name_format in image.name:
                filtered_images.append(image)

        if filtered_images and len(filtered_images) > retention:
            filtered_images.sort(key=lambda img: img.creationDate, reverse=True)
            i = 0
            while i < retention:
                filtered_images.pop(0)
                i += 1

            for image in filtered_images:
                image.deregister()

        #Check if the purge works : current_version and current_version -1,2,3,4 are not removed.
        images = []
        filtered_images = []
        images = conn.get_all_images(owners="self")

        for image in images:
            if ami_name_format in image.name:
                filtered_images.append(image)

        if len(filtered_images) <= retention:
            return True
        else:
            return False

    def _format_packer_from_app(self, salt_skip_bootstrap_option):
        datas = {
            'region': self._app['region'],
            'ami_name': self._ami_name,
            'source_ami': self._app['build_infos']['source_ami'],
            'instance_type': self._job['instance_type'],
            'ssh_username': self._app['build_infos']['ssh_username'],
            'vpc_id': self._app['vpc_id'],
            'subnet_id': self._app['build_infos']['subnet_id'],
            'associate_public_ip_address': '1',
            'skip_salt_bootstrap': salt_skip_bootstrap_option,
            'ami_block_device_mappings': [],
            'iam_instance_profile': self._app['environment_infos']['instance_profile'],
            'credentials': self._cloud_connection.get_credentials()
        }

        for opt_vol in self._app['environment_infos'].get('optional_volumes'):
            block = {
                'device_name': opt_vol['device_name'],
                'volume_type': opt_vol['volume_type'],
                'volume_size': opt_vol['volume_size'],
                'delete_on_termination': True
            }
            if 'iops' in opt_vol:
                block['iops'] = opt_vol['iops']
            datas['ami_block_device_mappings'].append(block)

        return json.dumps(datas, sort_keys=True, indent=4, separators=(',', ': '))

    def _format_salt_top_from_app_features(self):
        """ Generates the formula dictionnary object with all required features
        >>> class worker:
        ...     app = { \
                    'name': 'AppName', 'env': 'prod', 'role': 'webfront', 'region': 'eu-west-1',\
                    'features': [{'name': 'pkg', 'version': 'git_vim'}, {'name': 'pkg', 'version': 'package=lsof'}, {'name': 'pkg', 'version': 'package=curl'}]\
                 }
        ...     job = None
        ...     log_file = None
        ...     _config = None
        ...     _db = None
        >>> Buildimage(worker=worker())._format_salt_top_from_app_features()
        ['pkg']
        """
        top = []
        for i in self._app['features']:
            if re.search('^(php|php5)-(.*)',i['name']):
                continue
            if re.search('^zabbix-(.*)',i['name']):
                continue
            if re.search('^gem-(.*)',i['name']):
                continue
            if not i['name'].encode('utf-8') in top:
                top.append(i['name'].encode('utf-8'))
        return top

    def _format_salt_pillar_from_app_features(self):
        """ Generates the pillar dictionnary object with all required features and their options
        >>> class worker:
        ...     app = { \
                    'name': 'AppName', 'env': 'prod', 'role': 'webfront', 'region': 'eu-west-1',\
                    'features': [{'name': 'pkg', 'version': 'git_vim'}, {'name': 'pkg', 'version': 'package=lsof'}, {'name': 'pkg', 'version': 'package=curl'}]\
                 }
        ...     job = None
        ...     log_file = None
        ...     _config = None
        ...     _db = None
        >>> import pprint
        >>> pprint.pprint(Buildimage(worker=worker())._format_salt_pillar_from_app_features().items())
        [('pkg', {'package': ['lsof', 'curl'], 'version': 'git_vim'})]
        """
        pillar = {}
        for ft in self._app['features']:
            values = ft['version'].split('=', 1) # Split only one time
            feature_name = ft['name'].encode('utf-8')
            if not feature_name in pillar:
                pillar[feature_name] = {}
            if len(values) == 2:
                ft_param_key = values[0].encode('utf-8')
                ft_param_val = values[1].encode('utf-8')
                if not ft_param_key in pillar[feature_name]:
                    pillar[feature_name][ft_param_key] = []
                pillar[feature_name][ft_param_key].append(ft_param_val)
            else:
                pillar[feature_name]['version'] = ft['version'].encode('utf-8')
        return pillar

    def _update_app_ami(self, ami_id):
            self._db.apps.update({'_id': self._app['_id']},{'$set': {'ami': ami_id, 'build_infos.ami_name': self._ami_name}})
            self._worker.update_status("done")

    def _generate_buildimage_hook(self, hook_name):
        log("Create '%s' script for Packer" % hook_name, self._log_file)
        lfc_hooks = self._app.get('lifecycle_hooks', None)
        if not lfc_hooks or not lfc_hooks.get(hook_name, None):
            hook_source = u''
        else:
            hook_source = b64decode_utf8(self._app['lifecycle_hooks'][hook_name])
        app_path = "/ghost/{name}/{env}/{role}".format(name=self._app['name'], env=self._app['env'], role=self._app['role'])
        if not os.path.exists(app_path):
            os.makedirs(app_path)
        hook_file_path = "{app_path}/hook-{hook_name}".format(app_path=app_path, hook_name=hook_name)
        with io.open(hook_file_path, mode='w', encoding='utf-8') as f:
            f.write(hook_source)
        return hook_file_path

    def _get_buildimage_hooks(self):
        hooks = {}
        hooks['pre_buildimage'] = self._generate_buildimage_hook('pre_buildimage')
        hooks['post_buildimage'] = self._generate_buildimage_hook('post_buildimage')
        return hooks

    def _get_notification_message_done(self, ami_id):
        """
        >>> from bson.objectid import ObjectId
        >>> class worker:
        ...   app = {'name': 'AppName', 'env': 'prod', 'role': 'webfront', 'region': 'eu-west-1'}
        ...   job = None
        ...   log_file = None
        ...   _config = None
        ...   _db = None
        >>> Buildimage(worker=worker())._get_notification_message_done('')
        'Build image OK: []'
        >>> Buildimage(worker=worker())._get_notification_message_done('012345678901234567890123')
        'Build image OK: [012345678901234567890123]'
        """
        return 'Build image OK: [{0}]'.format(ami_id)

    def execute(self):
        skip_salt_bootstrap_option = self._job['options'][0] if 'options' in self._job and len(self._job['options']) > 0 else True
        json_packer = self._format_packer_from_app(skip_salt_bootstrap_option)
        json_packer_for_log = json.loads(json_packer)
        del json_packer_for_log['credentials']
        log("Generating a new AMI", self._log_file)
        log("Packer options : %s" %json.dumps(json_packer_for_log, sort_keys=True, indent=4, separators=(',', ': ')), self._log_file)
        pack = Packer(json_packer, self._config, self._log_file, self._job['_id'])
        ami_id = pack.build_image(self._format_salt_top_from_app_features(), self._format_salt_pillar_from_app_features(), self._get_buildimage_hooks())
        if ami_id is not "ERROR":
            log("Update app in MongoDB to update AMI: {0}".format(ami_id), self._log_file)
            self._update_app_ami(ami_id)
            if (self._purge_old_images()):
                log("Old AMIs removed for this app", self._log_file)
            else:
                log("Purge old AMIs failed", self._log_file)
            if self._app['autoscale']['name']:
                if check_autoscale_exists(self._cloud_connection, self._app['autoscale']['name'], self._app['region']):
                    userdata = None
                    launch_config = None
                    userdata = generate_userdata(self._config['bucket_s3'], self._config.get('bucket_region', self._app['region']), self._config['ghost_root_path'])
                    if userdata:
                        launch_config = create_launch_config(self._cloud_connection, self._app, userdata, ami_id)
                        log("Launch configuration [{0}] created.".format(launch_config.name), self._log_file)
                        if launch_config:
                            update_auto_scale(self._cloud_connection, self._app, launch_config, self._log_file)
                            if (purge_launch_configuration(self._cloud_connection, self._app, self._config.get('launch_configuration_retention', 5))):
                                log("Old launch configurations removed for this app", self._log_file)
                            else:
                                log("ERROR: Purge launch configurations failed", self._log_file)
                            self._worker.update_status("done", message=self._get_notification_message_done(ami_id))
                        else:
                            log("ERROR: Cannot update autoscaling group", self._log_file)
                            self._worker.update_status("failed")
                    else:
                        log("ERROR: Cannot generate userdata. The bootstrap.sh file can maybe not be found.", self._log_file)
                        self._worker.update_status("failed")
                else:
                    log("ERROR: Autoscaling group [{0}] does not exist".format(self._app['autoscale']['name']), self._log_file)
                    self._worker.update_status("failed")
            else:
                log("No autoscaling group name was set", self._log_file)
                self._worker.update_status("done")
        else:
            log("ERROR: ami_id not found. The packer process had maybe fail.", self._log_file)
            self._worker.update_status("failed")
