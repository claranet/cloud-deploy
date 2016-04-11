from boto.ec2.instancetype import InstanceType

import json

with open('aws_data_instance_types.json') as data_file:
    data = json.load(data_file)

instance_types = {}

# Instance types from China (cn-north-1) region are not available like in others

instance_types['cn-north-1'] = {
    InstanceType(name='t2.micro',   cores='1',  memory='1',    disk='EBS only'),
    InstanceType(name='t2.small',   cores='1',  memory='2',    disk='EBS only'),
    InstanceType(name='t2.medium',  cores='2',  memory='4',    disk='EBS only'),
    InstanceType(name='t2.large',   cores='2',  memory='8',    disk='EBS only'),
    InstanceType(name='m1.small',   cores='1',  memory='1.7',  disk='1 x 160'),
    InstanceType(name='m3.medium',  cores='1',  memory='3.75', disk='1 x 4 SSD'),
    InstanceType(name='m3.large',   cores='2',  memory='7.5',  disk='1 x 32 SSD'),
    InstanceType(name='m3.xlarge',  cores='4',  memory='15',   disk='2 x 40 SSD'),
    InstanceType(name='m3.2xlarge', cores='8',  memory='30',   disk='2 x 80 SSD'),
    InstanceType(name='c4.large',   cores='2',  memory='3.75', disk='EBS only'),
    InstanceType(name='c4.xlarge',  cores='4',  memory='7.5',  disk='EBS only'),
    InstanceType(name='c4.2xlarge', cores='8',  memory='15',   disk='EBS only'),
    InstanceType(name='c4.4xlarge', cores='16', memory='30',   disk='EBS only'),
    InstanceType(name='c4.8xlarge', cores='36', memory='60',   disk='EBS only'),
    InstanceType(name='c3.large',   cores='2',  memory='3.75', disk='2 x 16 SSD'),
    InstanceType(name='c3.xlarge',  cores='4',  memory='7.5',  disk='2 x 40 SSD'),
    InstanceType(name='c3.2xlarge', cores='8',  memory='15',   disk='2 x 80 SSD'),
    InstanceType(name='c3.4xlarge', cores='16', memory='30',   disk='2 x 160 SSD'),
    InstanceType(name='c3.8xlarge', cores='32', memory='60',   disk='2 x 320 SSD'),
    InstanceType(name='r3.large',   cores='2',  memory='15',   disk='1 x 32 SSD'),
    InstanceType(name='r3.xlarge',  cores='4',  memory='30.5', disk='1 x 80 SSD'),
    InstanceType(name='r3.2xlarge', cores='8',  memory='61',   disk='1 x 160 SSD'),
    InstanceType(name='r3.4xlarge', cores='16', memory='122',  disk='1 x 320 SSD'),
    InstanceType(name='r3.8xlarge', cores='32', memory='244',  disk='2 x 320 SSD'),
    InstanceType(name='i2.xlarge',  cores='4',  memory='30.5', disk='1 x 800 SSD'),
    InstanceType(name='i2.2xlarge', cores='8',  memory='61',   disk='2 x 800 SSD'),
    InstanceType(name='i2.4xlarge', cores='16', memory='122',  disk='4 x 800 SSD'),
    InstanceType(name='i2.8xlarge', cores='32', memory='244',  disk='8 x 800 SSD'),
} # yapf: disable

for region_data in data:
    region = region_data['region']
    instance_types[region] = []

    instanceTypes = region_data['instanceTypes']
    for generation in instanceTypes:
        generation_type = generation['type']
        for size in generation['sizes']:
            instance_types[region].append(InstanceType(name=size['size'],
                                                       cores=size['vCPU'],
                                                       memory=size[
                                                           'memoryGiB'],
                                                       disk=size['storageGB']))
