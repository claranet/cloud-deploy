from fabric.colors import green as _green, yellow as _yellow, red as _red
import os
import time
from jinja2 import Environment, FileSystemLoader
from settings import cloud_connections, DEFAULT_PROVIDER

from ghost_log import log
from ghost_aws import create_block_device, generate_userdata
from ghost_tools import get_aws_connection_data

COMMAND_DESCRIPTION = "Create a new instance"

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
        self._connection_data = get_aws_connection_data(
                self._app.get('assumed_account_id', ''),
                self._app.get('assumed_role_name', '')
                )
        self._cloud_connection = cloud_connections.get(self._app.get('provider', DEFAULT_PROVIDER))(
                self._log_file,
                **self._connection_data
                )


    def _create_server(self):
        root_ghost_path=os.path.dirname(os.path.dirname(os.path.realpath(os.path.realpath(__file__))))

        log(_green("STATE: Started"), self._log_file)
        log(_yellow(" INFO: Creating User-Data"), self._log_file)
        userdata = generate_userdata(self._config['bucket_s3'], self._config.get('bucket_region', self._app['region']), root_ghost_path)

        log(_yellow(" INFO: Creating EC2 instance"), self._log_file)
        if self._app['ami']:
            log(" CONF: AMI: {0}".format(self._app['ami']), self._log_file)
            log(" CONF: Region: {0}".format(self._app['region']), self._log_file)
            try:
                conn = self._cloud_connection.get_connection(self._app['region'], ["ec2"])
                image = self._app['ami']
                interface = self._cloud_connection.launch_service(
                        ["ec2", "networkinterface", "NetworkInterfaceSpecification"], 
                        subnet_id=self._app['environment_infos']['subnet_ids'][0],
                        groups=self._app['environment_infos']['security_groups'],
                        associate_public_ip_address=True
                        )
                interfaces = self._cloud_connection.launch_service(
                        ["ec2", "networkinterface", "NetworkInterfaceCollection"],
                        interface
                        )
                if 'root_block_device' in self._app['environment_infos']:
                    bdm = create_block_device(self._cloud_connection, self._app['region'], self._app['environment_infos']['root_block_device'])
                else:
                    bdm = create_block_device(self._cloud_connection, self._app['region'], {})
                reservation = conn.run_instances(image_id=self._app['ami'], \
                        key_name=self._app['environment_infos']['key_name'], \
                        network_interfaces=interfaces, \
                        instance_type=self._app['instance_type'], \
                        instance_profile_name=self._app['environment_infos']['instance_profile'], \
                        user_data=userdata, block_device_map=bdm)

                #Getting instance metadata
                instance = reservation.instances[0]
                if instance.id:
                    #Adding tags from app
                    conn.create_tags([instance.id], {"Name":"ec2.{0}.{1}.{2}".format(self._app['env'], self._app['role'], self._app['name'])})
                    conn.create_tags([instance.id], {"env":self._app['env']})
                    conn.create_tags([instance.id], {"role":self._app['role']})
                    conn.create_tags([instance.id], {"app":self._app['name']})
                    conn.create_tags([instance.id], {"app_id":self._app['_id']})
                    #Check instance state
                    while instance.state == u'pending':
                        log(_yellow("STATE: Instance state: %s" % instance.state), self._log_file)
                        time.sleep(10)
                        instance.update()

                    log(" CONF: Public IP: %s" % instance.ip_address, self._log_file)
                    self._worker.update_status("done", message="Creating Instance OK: [{0}]\n\nPublic IP: {1}".format(self._app['name'], str(instance.ip_address)))
                    log(_green("STATE: Instance state: %s" % instance.state), self._log_file)
                else:
                    log(_red("ERROR: Cannot get instance metadata. Please check the AWS Console."), self._log_file)
                log(_green("STATE: End"), self._log_file)
            except IOError as e:
                log(_red("I/O error({0}): {1}".format(e.errno, e.strerror)), self._log_file)
        else:
                log(_red("ERROR: No AMI set, please use buildimage before"), self._log_file)
                self._worker.update_status("failed", message="Creating Instance Failed: [{0}]\n{1}".format(self._app['name'], str(e)))
                log(_red("STATE: END"), self._log_file)

        return instance.ip_address

    def execute(self):
        self._create_server()
