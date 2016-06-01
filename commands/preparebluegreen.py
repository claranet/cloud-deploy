from fabric.colors import green as _green, yellow as _yellow, red as _red

from ghost_log import log

COMMAND_DESCRIPTION = "Prepare the Blue/Green env before swap"

class Preparebluegreen():
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

    def execute(self):
        log(_green("STATE: Started"), self._log_file)
        # Check if app has blue green enabled, if is not online
        # Check if app has AS
        # Check if app has up to date AMI
        # Check if all module have been deployed
        # Check if instances are already running
        # Create the testing ELB : {uid}-{app-name}-{env}-{role}-bluegreen, duplicated from the PROD ELB
        # Update auto scale : attach testing ELB, update LaunchConfig, update AS value (duplicate from PROD/online AS)
        # Return / print Testing ELB url/dns
        self._worker.update_status("done", message="DUMMY: [{0}]".format(self._app['name']))
