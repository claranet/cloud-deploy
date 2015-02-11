from subprocess import call

class GCallException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def gcall(args, cmd_description, log_fd):
    log("CMD: %s" % cmd_description, log_fd)
    if not self._dry_run:
        ret = call(args, stdout=log_fd, stderr=log_fd, shell=True)
        if (ret != 0):
            raise GCallException("ERROR: %s" % cmd_description)

def log(message, fd):
    fd.write("{message}\n".format(message=message))

