from flask.ext.socketio import SocketIO, emit
import os
import gevent

LOG_ROOT='/var/log/ghost'

def create_ws(app):
    socketio = SocketIO(app)

    def follow(filename):
        last_pos = 0
        hub = gevent.get_hub()
        print(hub)
        watcher = hub.loop.stat(filename)
        try:
            with open(filename) as f:
                while True:
                    f.seek(last_pos)
                    for line in f:
                        emit('job', line)
                    last_pos = f.tell()
                    hub.wait(watcher)
        except IOError:
            emit('job', 'Log file not ready yet')

    @socketio.on('job_logging')
    def handle_message(data):
        if data and data.get('log_id'):
            log_id = data.get('log_id')
            filename = LOG_ROOT + '/' + log_id + '.txt'
            filename = filename.encode('ascii', 'ignore')
            print('Streaming log: {0}'.format(filename))
            follow(filename)

    return socketio
