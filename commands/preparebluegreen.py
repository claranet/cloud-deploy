"""Classes pertaining to blue/green preparation."""
from fabric.colors import green as _green, yellow as _yellow, red as _red

from ghost_log import log

COMMAND_DESCRIPTION = "Prepare the Blue/Green env before swap"


class Preparebluegreen(object):
    """Checks and prepares blue/green deployment before swap."""

    _app = None
    _job = None
    _log_file = -1

    def __init__(self, worker):
        """init from worker attributes."""
        self._app = worker.app
        self._job = worker.job
        self._db = worker._db
        self._config = worker._config
        self._worker = worker
        self._log_file = worker.log_file

    def _check_blue_green_enabled(self):
        """Check if blue/green deployment is enabled for this app."""
        if not self._app.get('blue_green', None):
            message = 'blue/green is not enabled for this app'
            log(_red('ERROR: ' + message),
                self._log_file)
            self._worker.update_status("failed", message=message)
            return False
        return True

    def execute(self):
        """Execute all checks and preparations."""
        log(_green("STATE: Started"), self._log_file)

        # Check if app has blue green enabled, if is not online
        if not self._check_blue_green_enabled():
            return

        # Check if app has AS
        # Check if app has up to date AMI
        # Check if all module have been deployed
        # Check if instances are already running
        # Create the testing ELB : {uid}-{app-name}-{env}-{role}-bluegreen, duplicated from the PROD ELB
        # Update auto scale : attach testing ELB, update LaunchConfig, update AS value (duplicate from PROD/online AS)
        # Return / print Testing ELB url/dns
        self._worker.update_status("done", message="DUMMY: [{0}]".format(self._app['name']))
