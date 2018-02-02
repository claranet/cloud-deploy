# -*- coding: utf-8 -*-

import json

from pypacker import Packer
from ghost_tools import get_aws_connection_data
from settings import cloud_connections, DEFAULT_PROVIDER
from ghost_log import log

from .image_builder import ImageBuilder


class AWSImageBuilder(ImageBuilder):
    """
    This class is designed to Build an AWS AMI using Packer
    """
    def __init__(self, app, job, db, log_file, config):
        ImageBuilder.__init__(self, app, job, db, log_file, config)
        self._connection_data = get_aws_connection_data(
                self._app.get('assumed_account_id', ''),
                self._app.get('assumed_role_name', ''),
                self._app.get('assumed_region_name', '')
                )
        self._cloud_connection = cloud_connections.get(self._app.get('provider', DEFAULT_PROVIDER))(
                self._log_file,
                **self._connection_data
                )

    def _format_packer_from_app(self, provisioner_skip_bootstrap_option):
        instance_tags = {}
        if 'instance_tags' in self._app['environment_infos']:
            instance_tags = {i['tag_name']: i['tag_value'] for i in self._app['environment_infos']['instance_tags']}
        data = {
            'region': self._app['region'],
            'ami_name': self._ami_name,
            'source_ami': self._app['build_infos']['source_ami'],
            'instance_type': self._job['instance_type'],
            'ssh_username': self._app['build_infos']['ssh_username'],
            'ssh_private_ip': '1',
            'vpc_id': self._app['vpc_id'],
            'subnet_id': self._app['build_infos']['subnet_id'],
            'associate_public_ip_address': '1',
            'skip_provisioner_bootstrap': provisioner_skip_bootstrap_option,
            'ami_block_device_mappings': [],
            'launch_block_device_mappings': [],
            'iam_instance_profile': self._app['environment_infos']['instance_profile'],
            'credentials': self._cloud_connection.get_credentials(),
            'tags': instance_tags,
            'ghost_env_vars': self._format_ghost_env_vars(),
            'custom_env_vars': self._app.get('env_vars', []),
            'security_group_ids': self._app['environment_infos']['security_groups']
        }

        for opt_vol in self._app['environment_infos'].get('optional_volumes', []):
            block = {
                'device_name': opt_vol['device_name'],
                'volume_type': opt_vol['volume_type'],
                'volume_size': opt_vol['volume_size'],
                'delete_on_termination': True
            }
            if 'iops' in opt_vol:
                block['iops'] = opt_vol['iops']
            data['ami_block_device_mappings'].append(block)

            if 'launch_block_device_mappings' in opt_vol:
                data['launch_block_device_mappings'].append(block)

        return json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))

    def start_builder(self):
        provisioner_bootstrap_option = self._job['options'][0] if 'options' in self._job and len(self._job['options']) > 0 else True
        json_packer = self._format_packer_from_app(provisioner_bootstrap_option)
        json_packer_for_log = json.loads(json_packer)
        del json_packer_for_log['credentials']
        log("Generating a new AMI", self._log_file)
        log("Packer options : %s" %json.dumps(json_packer_for_log, sort_keys=True, indent=4, separators=(',', ': ')), self._log_file)
        pack = Packer(json_packer, self._config, self._log_file, self._job['_id'])
        ami_id = pack.build_image(self._app['features'], self._get_buildimage_hooks())
        return ami_id, self._ami_name

    def purge_old_images(self):
        conn = self._cloud_connection.get_connection(self._app['region'], ["ec2"])
        retention = self._config.get('ami_retention', 5)
        filtered_images = []
        images = conn.get_all_images(owners="self")
        ami_name_format = self._ami_name

        for image in images:
            # log(image.name, self._log_file)
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

        # Check if the purge works : current_version and current_version -1,2,3,4 are not removed.
        filtered_images = []
        images = conn.get_all_images(owners="self")

        for image in images:
            if ami_name_format in image.name:
                filtered_images.append(image)

        return len(filtered_images) <= retention
