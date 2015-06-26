from boto.ec2.instancetype import InstanceType
from boto.vpc import VPC

instance_types = [
    InstanceType(name='t2.micro', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='t2.small', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='t2.medium', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='t2.large', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='m4.large', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='m4.xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='m4.2xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='m4.4xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='m4.10xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='m3.large', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='m3.xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='m3.2xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='c4.large', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='c4.xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='c4.2xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='c4.4xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='c4.8xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='c3.large', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='c3.xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='c3.2xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='c3.4xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='c3.8xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='g2.xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='r3.large', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='r3.xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='r3.4xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='r3.8xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='i2.xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='i2.2xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='i2.4xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='i2.8xlarge', cores='N/A', memory='N/A', disk='N/A'),
    InstanceType(name='hs1.8xlarge')
]


dummy_vpcs = [
    VPC()
]
dummy_vpcs[0].id = 'vpc-0'
dummy_vpcs[0].tags['Name'] = 'dummy'