import time
import json
from commands.pypacker import Packer
from commands.tools import log
import re
from fabric.api import *
from fabric.colors import green as _green, yellow as _yellow
import boto
import boto.ec2
from config import *
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


    def create_server():
        iamrole = ""
        secgroup = "sg-11c7b474"
        """
        Creates EC2 Instance
        """
        print(_green("Started..."))
        print(_yellow("...Creating EC2 instance..."))

        if(self._app.ami):
            print("AMI: {0}".format(self._app.ami))
            print("Region: {0}".format(self._app.region))
            #conn = boto.ec2.connect_to_region(ec2_region, aws_access_key_id=ec2_key, aws_secret_access_key=ec2_secret)
            conn = boto.ec2.connect_to_region(self._app.region)
            #image = conn.get_all_images(ec2_amis)
            image = self._app.ami
        else:
            print("No AMI set, please use buildimage before")


        reservation = ec2.run_instances(image_id=image, 1, key_name=ec2_key_pair, security_groups=ec2_security, instance_type="t2.micro")

        instance = reservation.instances[0]
        conn.create_tags([instance.id], {"Name":config['INSTANCE_NAME_TAG']})
        while instance.state == u'pending':
            print(_yellow("Instance state: %s" % instance.state))
            time.sleep(10)
            instance.update()

        print(_green("Instance state: %s" % instance.state))
        print(_green("Public IP: %s" % instance.publicip))

        return instance.publicip

    def execute():



