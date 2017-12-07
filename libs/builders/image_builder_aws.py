# -*- coding: utf-8 -*-

import json

from pypacker import Packer
from ghost_tools import get_aws_connection_data
from settings import cloud_connections, DEFAULT_PROVIDER
from ghost_log import log

from libs.ec2 import get_ami_root_block_device_mapping
from libs.builders.image_builder import ImageBuilder


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

        self._packer_file_path_aws = self.packer_file_path + "/aws_builder.json"


    def _format_packer_from_app(self):
        instance_tags = {}
        if 'instance_tags' in self._app['environment_infos']:
            instance_tags = {i['tag_name']: i['tag_value'] for i in self._app['environment_infos']['instance_tags']}
        data = {
            'type': 'amazon-ebs',
            'region': self._app['region'],
            'ami_name': self._ami_name,
            'source_ami': self._app['build_infos']['source_ami'],
            'instance_type': self._job['instance_type'],
            'ssh_username': self._app['build_infos']['ssh_username'],
            'ssh_interface': 'private_ip',
            'vpc_id': self._app['vpc_id'],
            'subnet_id': self._app['build_infos']['subnet_id'],
            'associate_public_ip_address': True,
            'ami_block_device_mappings': [],
            'launch_block_device_mappings': [],
            'iam_instance_profile': self._app['environment_infos']['instance_profile'],
            'tags': instance_tags,
            'security_group_ids': self._app['environment_infos']['security_groups']
        }

        if 'root_block_device' in self._app['environment_infos']:
            root_vol = self._app['environment_infos']['root_block_device']
            if root_vol.get('name'):
                root_vol_path = root_vol['name']
            else:
                root_vol_path = get_ami_root_block_device_mapping(self._cloud_connection.get_connection(self._app['region'], ["ec2"]),
                                                                  self._app['build_infos']['source_ami'])
            block = {
                'device_name': root_vol_path,
                'volume_type': 'gp2',
                'volume_size': root_vol.get('size', 20),
                'delete_on_termination': True,
            }
            data['launch_block_device_mappings'].append(block)

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

        return data

    def _build_packer_json(self):
        packer = {}
        builders = [self._format_packer_from_app()]
        packer['builders'] = builders
        packer['provisioners'] = self._get_packer_provisionners
        log('packer file path: {0}'.format(self.packer_file_path), self._log_file)
        stream = file(self._packer_file_path_aws, 'w')
        log("Writing Packer definition to: {0}".format(self.packer_file_path), self._log_file)
        json.dump(packer, stream, sort_keys=True, indent=4, separators=(',', ': '))
        return packer

    def start_builder(self):
        packer = self._build_packer_json()
        credentials = self._cloud_connection.get_credentials()
        log("Generating a new AMI", self._log_file)
        log("Packer options : %s" %json.dumps(packer, sort_keys=True, indent=4, separators=(',', ': ')), self._log_file)
        pack = Packer(credentials, self._log_file)
        ami_id = pack.build_image(self._packer_file_path_aws)
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
