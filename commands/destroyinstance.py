from commands.tools import log
from base64 import b64encode
from fabric.api import *
from fabric.colors import green as _green, yellow as _yellow, red as _red
import boto
import boto.ec2
import os
import time
from jinja2 import Environment, FileSystemLoader


class Destroyinstance():
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


    def _destroy_server(self):
        log(_green("STATE: Started"), self._log_file)
        log(_yellow(" INFO: Destroy EC2 instance"), self._log_file)
        log(" CONF: AMI: {0}".format(self._app['ami']), self._log_file)
        log(" CONF: Region: {0}".format(self._app['region']), self._log_file)
        try:
            conn = boto.ec2.connect_to_region(self._app['region'])
            reservations = conn.get_all_instances(filters={"tag:app_id" : self._app['_id']})
            #Terminating instances
            instances = []
            for r in reservations:
                  for i in r.instances:
                        instances.append(i.id)
            log(instances, self._log_file)
            conn.terminate_instances(instance_ids=instances)

            self._worker.update_status("done", message="Instance deletion OK: [{0}]".format(self._app['name']))
            log(_green("STATE: Instance state: %s" % instance.state), self._log_file)
            log(_green("STATE: End"), self._log_file)
        except IOError as e:
            log(_red("I/O error({0}): {1}".format(e.errno, e.strerror)), self._log_file)
            self._worker.update_status("failed", message="Creating Instance Failed: [{0}]\n{1}".format(self._app['name'], str(e)))
            log(_red("STATE: END"), self._log_file)


    def execute(self):
        self._destroy_server()
