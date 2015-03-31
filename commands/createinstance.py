import time
import json
from commands.pypacker import Packer
from commands.tools import log
import re
from fabric.api import *
from fabric.colors import green as _green, yellow as _yellow
import boto
import boto.ec2
#from config import *
import time


class Createinstance():
    _app = None
    _job = None
    _log_file = -1

    def __init__(self, worker):
        self._app = worker.app
        self._job = worker.job
        self._db = worker._db
        self._worker = worker
        self._log_file = worker.log_file


    def _create_server(self):
        secgroup = "sg-fc236099"
        instance_profile = "ec2.kevin-instance"
        #ami = "ami-ddd64caa"
        key = "kevin"
        instance_type = "t2.micro"
        subnet_id = "subnet-e613ce83"

        """
        Creates EC2 Instance
        """
        print(_green("Started..."))
        print(_yellow("...Creating EC2 instance..."))

        if(self._app.ami):
            print("AMI: {0}".format(self._app.ami))
            print("Region: {0}".format(self._app.region))
            conn = boto.ec2.connect_to_region(self._app.region)
            image = self._app.ami
            interface = boto.ec2.networkinterface.NetworkInterfaceSpecification( \
                    subnet_id=self._app.environment_infos.subnet_ids[0], \
                    groups=self._app.environment_infos.security_groups, \
                    associate_public_ip_address=True)
            interfaces = boto.ec2.networkinterface.NetworkInterfaceCollection(interface)
            reservation = conn.run_instances(image_id=self._app.ami, \
                    key_name=self._app.environment_infos.key_name, \
                    network_interfaces=interfaces, \
                    instance_type=self._app.instance_type, \
                    instance_profile_name=self._app.environment_infos.instance_profile)
            instance = reservation.instances[0]
            conn.create_tags([instance.id], {"Name":config['INSTANCE_NAME_TAG']})
            while instance.state == u'pending':
                print(_yellow("Instance state: %s" % instance.state))
                time.sleep(10)
                instance.update()

            print(instance)
            print(_green("Instance state: %s" % instance.state))
            print(_green("Public IP: %s" % instance.publicip))
        else:
            print("No AMI set, please use buildimage before")


        return instance.publicip

    def execute(self):
        #newInstance = Createinstance()
        self._create_server()



