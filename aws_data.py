from boto.ec2.instancetype import InstanceType

import json

with open('aws_data_instance_types.json') as data_file:
    data = json.load(data_file)

instance_types = {}

for region_data in data:
    region = region_data['region']
    instance_types[region] = []

    instanceTypes = region_data['instanceTypes']
    for generation in instanceTypes:
        generation_type = generation['type']
        for size in generation['sizes']:
            instance_types[region].append(InstanceType(name=size['size'], cores=size['vCPU'], memory=size['memoryGiB'], disk=size['storageGB']))
