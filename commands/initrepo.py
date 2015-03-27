import os
from pymongo import MongoClient
from commands.tools import GCallException, gcall, log

class InitRepo():

    def __init__(app, job, log_fd):
        self._app = app
        self._job = job
        self._log_fd = log_fd


    def _init_module(self, options={}):
        os.chdir("/ghost")
        try:
            os.makedirs("{app}/{env}/{role}".format(**self._app))
        except:
            raise CallException("Init app, creating directory")
        os.chdir("/ghost/{app}/{env}/{role}".format(**self._app))
        self._gcall("git clone --recursive {git_repo}".format(**self._app), "Git clone")
        os.chdir(self._git_repo)

    def execute():
        _init_module()


