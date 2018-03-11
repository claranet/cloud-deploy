from boto.ec2.instancetype import InstanceType

import json

instance_types = {}

# Instance types from China (cn-north-1) region are not available like in others

instance_types['cn-north-1'] = {
    InstanceType(name='t1.micro',    cores='1',  memory='0.613', disk='EBS only'),
    InstanceType(name='t2.micro',    cores='1',  memory='1',     disk='EBS only'),
    InstanceType(name='t2.small',    cores='1',  memory='2',     disk='EBS only'),
    InstanceType(name='t2.medium',   cores='2',  memory='4',     disk='EBS only'),
    InstanceType(name='t2.large',    cores='2',  memory='8',     disk='EBS only'),
    InstanceType(name='m4.large',    cores='2',  memory='8',     disk='EBS only'),
    InstanceType(name='m4.xlarge',   cores='4',  memory='16',    disk='EBS only'),
    InstanceType(name='m4.2xlarge',  cores='8',  memory='32',    disk='EBS only'),
    InstanceType(name='m4.4xlarge',  cores='16', memory='64',    disk='EBS only'),
    InstanceType(name='m4.10xlarge', cores='40', memory='160',   disk='EBS only'),
    InstanceType(name='m4.16xlarge', cores='64', memory='256',   disk='EBS only'),
    InstanceType(name='m3.medium',   cores='1',  memory='3.75',  disk='1 x 4 SSD'),
    InstanceType(name='m3.large',    cores='2',  memory='7.5',   disk='1 x 32 SSD'),
    InstanceType(name='m3.xlarge',   cores='4',  memory='15',    disk='2 x 40 SSD'),
    InstanceType(name='m3.2xlarge',  cores='8',  memory='30',    disk='2 x 80 SSD'),
    InstanceType(name='m1.small',    cores='1',  memory='1.7',   disk='1 x 160'),
    InstanceType(name='c4.large',    cores='2',  memory='3.75',  disk='EBS only'),
    InstanceType(name='c4.xlarge',   cores='4',  memory='7.5',   disk='EBS only'),
    InstanceType(name='c4.2xlarge',  cores='8',  memory='15',    disk='EBS only'),
    InstanceType(name='c4.4xlarge',  cores='16', memory='30',    disk='EBS only'),
    InstanceType(name='c4.8xlarge',  cores='36', memory='60',    disk='EBS only'),
    InstanceType(name='c3.large',    cores='2',  memory='3.75',  disk='2 x 16 SSD'),
    InstanceType(name='c3.xlarge',   cores='4',  memory='7.5',   disk='2 x 40 SSD'),
    InstanceType(name='c3.2xlarge',  cores='8',  memory='15',    disk='2 x 80 SSD'),
    InstanceType(name='c3.4xlarge',  cores='16', memory='30',    disk='2 x 160 SSD'),
    InstanceType(name='c3.8xlarge',  cores='32', memory='60',    disk='2 x 320 SSD'),
    InstanceType(name='r3.large',    cores='2',  memory='15',    disk='1 x 32 SSD'),
    InstanceType(name='r3.xlarge',   cores='4',  memory='30.5',  disk='1 x 80 SSD'),
    InstanceType(name='r3.2xlarge',  cores='8',  memory='61',    disk='1 x 160 SSD'),
    InstanceType(name='r3.4xlarge',  cores='16', memory='122',   disk='1 x 320 SSD'),
    InstanceType(name='r3.8xlarge',  cores='32', memory='244',   disk='2 x 320 SSD'),
    InstanceType(name='i2.xlarge',   cores='4',  memory='30.5',  disk='1 x 800 SSD'),
    InstanceType(name='i2.2xlarge',  cores='8',  memory='61',    disk='2 x 800 SSD'),
    InstanceType(name='i2.4xlarge',  cores='16', memory='122',   disk='4 x 800 SSD'),
    InstanceType(name='i2.8xlarge',  cores='32', memory='244',   disk='8 x 800 SSD'),
 } # yapf: disable

def load_instance_data(instance_types, filename):
    """
    >>> instance_types = {}
    >>> instance_types['cn-north-1'] = { InstanceType(name='t1.micro', cores='1', memory='0.613', disk='EBS only'), }
    >>> load_instance_data(instance_types, 'aws_data_instance_types.json')
    >>> load_instance_data(instance_types, 'aws_data_instance_types_previous.json')
    >>> { type.name: type for type in instance_types["cn-north-1"] }['t1.micro']
    InstanceType:t1.micro-1,0.613,EBS only
    >>> { type.name: type for type in instance_types["us-east-1"] }['t2.nano']
    InstanceType:t2.nano-1,0.5,ebsonly
    >>> { type.name: type for type in instance_types["us-east-1"] }['m3.medium']
    InstanceType:m3.medium-1,3.75,1 x 4 SSD
    >>> { type.name: type for type in instance_types["us-east-1"] }['c5.large']
    InstanceType:c5.large-2,4,ebsonly
    """

    with open(filename) as data_file:
        data = json.load(data_file)
    for region_data in data:
        region = region_data['region']
        if not region in instance_types:
            instance_types[region] = []

        instanceTypes = region_data['instanceTypes']
        for generation in instanceTypes:
            for size in generation['sizes']:
                instance_types[region].append(InstanceType(name=size['size'],
                                                        cores=size['vCPU'],
                                                        memory=size[
                                                            'memoryGiB'],
                                                        disk=size['storageGB']))

load_instance_data(instance_types, 'aws_data_instance_types.json')
load_instance_data(instance_types, 'aws_data_instance_types_previous.json')