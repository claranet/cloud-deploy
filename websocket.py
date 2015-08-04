from flask.ext.socketio import SocketIO, emit
import gevent
import re

LOG_ROOT='/var/log/ghost'

COLOR_DICT = {
    '0':  [(255, 255, 255), (255,255,255)],
    '31': [(255, 0, 0), (128, 0, 0)],
    '32': [(0, 255, 0), (0, 128, 0)],
    '33': [(255, 255, 0), (128, 128, 0)],
    '34': [(0, 0, 255), (0, 0, 128)],
    '35': [(255, 0, 255), (128, 0, 128)],
    '36': [(0, 255, 255), (0, 128, 128)],
}

COLOR_REGEX = re.compile(r'\[(?P<arg_1>\d+)(;(?P<arg_2>\d+)(;(?P<arg_3>\d+))?)?m')

BOLD_TEMPLATE = '<span style="color: rgb{}; font-weight: bolder">'
LIGHT_TEMPLATE = '<span style="color: rgb{}">'


def ansi_to_html(text):
    text = text.replace('[m', '</span>')

    def single_sub(match):
        argsdict = match.groupdict()
        if argsdict['arg_3'] is None:
            if argsdict['arg_2'] is None:
                color, bold = argsdict['arg_1'], 0
            else:
                bold, color = int(argsdict['arg_1']), argsdict['arg_2']
        else:
            color, bold = argsdict['arg_2'], int(argsdict['arg_3'])

        if bold:
            try:
                return BOLD_TEMPLATE.format(COLOR_DICT[color][1])
            except KeyError:
                print("Bold color: {0}".format(color))
            finally:
                return BOLD_TEMPLATE.format(COLOR_DICT['32'][1])
        try:
            return LIGHT_TEMPLATE.format(COLOR_DICT[color][0])
        except KeyError:
            print("arg_1: {0}, arg_2: {1}, arg_3: {2}".format(argsdict['arg_1'], argsdict['arg_2'], argsdict['arg_3']))
        return LIGHT_TEMPLATE.format(COLOR_DICT['31'][0])

    return COLOR_REGEX.sub(single_sub, text)

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
                        emit('job', ansi_to_html(line))
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
