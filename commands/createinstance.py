from commands.tools import log
from base64 import b64encode
from fabric.api import *
from fabric.colors import green as _green, yellow as _yellow
import boto
import boto.ec2
import os
import time
from jinja2 import Environment, FileSystemLoader


class Createinstance():
    _app = None
    _job = None
    _log_file = -1

    def __init__(self, worker):
        self._app = worker.app
        self._job = worker.job
        self._db = worker._db
        self._config = worker._config
        self._worker = worker
        self._log_file = worker.log_file


    def _create_server(self):
        #secgroup = "sg-fc236099"
        #instance_profile = "ec2.kevin-instance"
        #ami = "ami-ddd64caa"
        #key = "kevin"
        #instance_type = "t2.micro"
        #subnet_id = "subnet-e613ce83"
        root_ghost_path=os.path.dirname(os.path.dirname(os.path.realpath(os.path.        realpath(__file__))))

        log(_green("STATE: Started"), self._log_file)
        log(_yellow("INFO: Creating User-Data"), self._log_file)

        log(_yellow("INFO: Bootstrap path: %s/scripts" % root_ghost_path), self._log_file)
        loader=FileSystemLoader('%s/scripts' % root_ghost_path)
        jinja_env = Environment(loader=loader)
        template = jinja_env.get_template('bootstrap.sh')
        userdata = b64encode(template.render(bucket_s3=self._config['bucket_s3']))
        #log(userdata, self._log_file)

        log(_yellow("INFO: Creating EC2 instance"), self._log_file)
        if(self._app['ami']):
            log("AMI: {0}".format(self._app['ami']), self._log_file)
            log("Region: {0}".format(self._app['region']), self._log_file)
            conn = boto.ec2.connect_to_region(self._app['region'])
            image = self._app['ami']
            interface = boto.ec2.networkinterface.NetworkInterfaceSpecification( \
                    subnet_id=self._app['environment_infos']['subnet_ids'][0], \
                    groups=self._app['environment_infos']['security_groups'], \
                    associate_public_ip_address=True)
            interfaces = boto.ec2.networkinterface.NetworkInterfaceCollection(interface)
            reservation = conn.run_instances(image_id=self._app['ami'], \
                    key_name=self._app['environment_infos']['key_name'], \
                    network_interfaces=interfaces, \
                    instance_type=self._app['instance_type'], \
                    instance_profile_name=self._app['environment_infos']['instance_profile'], \
                    user_data=userdata)
            instance = reservation.instances[0]
            conn.create_tags([instance.id], {"Name":"ec2.{0}.{1}.{2}".format(self._app['env'], self._app['role'], self._app['name'])})
            conn.create_tags([instance.id], {"env":self._app['env']})
            conn.create_tags([instance.id], {"role":self._app['role']})
            conn.create_tags([instance.id], {"app":self._app['name']})
            while instance.state == u'pending':
                log(_yellow("Instance state: %s" % instance.state), self._log_file)
                time.sleep(10)
                instance.update()

            log(_green("Public IP: %s" % instance.ip_address), self._log_file)
            log(_green("Instance state: %s" % instance.state), self._log_file)
        else:
            print("No AMI set, please use buildimage before")
            self._worker.update_status("failed", message="Creating Instance Failed: [{0}]\n{1}".format(self._app['name'], str(e)))


        return instance.ip_address

    def execute(self):
        ip = self._create_server()
        self._worker.update_status("done", message="Deployment OK: [{0}]\nPublic IP: {1}".format(self._app['name'], str(ip)))


