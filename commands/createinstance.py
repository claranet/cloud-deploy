from fabric.colors import green as _green, yellow as _yellow, red as _red
import os
import time
from settings import cloud_connections, DEFAULT_PROVIDER

from ghost_log import log
from ghost_aws import create_block_device, generate_userdata
from ghost_tools import get_aws_connection_data
from libs.blue_green import get_blue_green_from_app

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
                self._app.get('assumed_role_name', ''),
                self._app.get('assumed_region_name', '')
                )
        self._cloud_connection = cloud_connections.get(self._app.get('provider', DEFAULT_PROVIDER))(
                self._log_file,
                **self._connection_data
                )
        blue_green, self._color = get_blue_green_from_app(self._app)

    def _create_server(self, private_ip_address, subnet_id):
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
                        subnet_id=subnet_id,
                        groups=self._app['environment_infos']['security_groups'],
                        associate_public_ip_address=True, private_ip_address=private_ip_address
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
                    # Tagging
                    tag_ec2_name = False
                    for ghost_tag_key, ghost_tag_val in {'app': 'name', 'app_id': '_id', 'env': 'env', 'role': 'role'}.iteritems():
                        log("Tagging instance [{id}] with '{tk}':'{tv}'".format(id=instance.id, tk=ghost_tag_key, tv=str(self._app[ghost_tag_val])), self._log_file)
                        conn.create_tags([instance.id], {ghost_tag_key: str(self._app[ghost_tag_val])})
                    if self._color:
                        log("Tagging instance [{id}] with '{tk}':'{tv}'".format(id=instance.id, tk='color', tv=self._color), self._log_file)
                        conn.create_tags([instance.id], {"color": self._color})
                    if 'instance_tags' in self._app['environment_infos']:
                        for app_tag in self._app['environment_infos']['instance_tags']:
                            log("Tagging instance [{id}] with '{tk}':'{tv}'".format(id=instance.id, tk=app_tag['tag_name'], tv=app_tag['tag_value']), self._log_file)
                            conn.create_tags([instance.id], {app_tag['tag_name']: app_tag['tag_value']})
                            if app_tag['tag_name'] == 'Name':
                                tag_ec2_name = True
                    if not tag_ec2_name:
                        ec2_name = "ec2.{0}.{1}.{2}".format(self._app['env'], self._app['role'], self._app['name'])
                        log("Tagging instance [{id}] with '{tk}':'{tv}'".format(id=instance.id, tk='Name', tv=ec2_name), self._log_file)
                        conn.create_tags([instance.id], {'Name': ec2_name})

                    #Check instance state
                    while instance.state == u'pending':
                        log(_yellow("STATE: Instance state: %s" % instance.state), self._log_file)
                        time.sleep(10)
                        instance.update()

                    log(" CONF: Private IP: %s" % instance.private_ip_address, self._log_file)
                    log(" CONF: Public IP: %s" % instance.ip_address, self._log_file)
                    log(" CONF: Public DNS: %s" % instance.public_dns_name, self._log_file)
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
        subnet_id = self._job['options'][0] if 'options' in self._job and len(self._job['options']) > 0 else None
        private_ip_address = self._job['options'][1] if 'options' in self._job and len(self._job['options']) > 1 else None
        self._create_server(private_ip_address, subnet_id)
