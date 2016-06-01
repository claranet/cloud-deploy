from fabric.colors import green as _green, yellow as _yellow, red as _red

from ghost_log import log

COMMAND_DESCRIPTION = "Swap the Blue/Green env"

class Swapbluegreen():
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
        self._worker.update_status("done", message="DUMMY: [{0}]".format(self._app['name']))
