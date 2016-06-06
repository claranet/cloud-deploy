from datetime import datetime

def log(message, fd):
    fd.write("{timestamp}: {message}\n".format(timestamp=datetime.now().strftime("%Y/%m/%d %H:%M:%S GMT"), message=message))
