from flask import request
from flask_socketio import SocketIO
import gevent
import re
from xml.sax.saxutils import escape

LOG_ROOT='/var/log/ghost'

COLOR_DICT = {
    '31': [(255, 0, 0), (128, 0, 0)],
    '32': [(0, 255, 0), (0, 128, 0)],
    '33': [(255, 255, 0), (128, 128, 0)],
    '34': [(0, 0, 255), (0, 0, 128)],
    '35': [(255, 0, 255), (128, 0, 128)],
    '36': [(0, 255, 255), (0, 128, 128)],
}

COLOR_REGEX = re.compile(r'(\^\[|\033)\[(?P<arg_1>\d+)(;(?P<arg_2>\d+)(;(?P<arg_3>\d+))?)?m(?P<text>.*?)(?=\^\[|\033|$)')

BOLD_TEMPLATE = '<span style="color: rgb{}; font-weight: bolder">{}</span>'
LIGHT_TEMPLATE = '<span style="color: rgb{}">{}</span>'


def ansi_to_html(text):
    """
    >>> ansi_to_html('')
    ''

    >>> ansi_to_html('Some text')
    'Some text'

    >>> ansi_to_html('\\033[31mSome red text')
    '<span style="color: rgb(255, 0, 0)">Some red text</span>'

    >>> ansi_to_html('\\033[31mSome red text\\033[0m')
    '<span style="color: rgb(255, 0, 0)">Some red text</span>'

    >>> ansi_to_html('^[[31mSome red text')
    '<span style="color: rgb(255, 0, 0)">Some red text</span>'

    >>> ansi_to_html('^[[31mSome red text')
    '<span style="color: rgb(255, 0, 0)">Some red text</span>'

    >>> ansi_to_html('^[[32mSome green text')
    '<span style="color: rgb(0, 255, 0)">Some green text</span>'

    >>> ansi_to_html('^[[34mSome blue text')
    '<span style="color: rgb(0, 0, 255)">Some blue text</span>'

    >>> ansi_to_html('^[[31;1mSome bold red text')
    '<span style="color: rgb(128, 0, 0); font-weight: bolder">Some bold red text</span>'

    >>> ansi_to_html('^[[32;1mSome bold green text')
    '<span style="color: rgb(0, 128, 0); font-weight: bolder">Some bold green text</span>'

    >>> ansi_to_html('^[[34;1mSome bold blue text')
    '<span style="color: rgb(0, 0, 128); font-weight: bolder">Some bold blue text</span>'

    >>> ansi_to_html('^[[99mSome unknown color text')
    'Some unknown color text'

    >>> ansi_to_html('^[[34;1mSome bold blue text^[[39mSome normal text')
    '<span style="color: rgb(0, 0, 128); font-weight: bolder">Some bold blue text</span>Some normal text'
    """

    def single_sub(match):
        argsdict = match.groupdict()

        bold = 0
        color = None
        for arg in [argsdict['arg_1'], argsdict['arg_2'], argsdict['arg_3']]:
            if arg is not None and arg == '1':
                bold = 1
            if arg is not None and arg in COLOR_DICT.keys():
                color = arg

        if color:
            rgb = COLOR_DICT[color][bold]
            template = bold and BOLD_TEMPLATE or LIGHT_TEMPLATE
            return template.format(rgb, argsdict['text'])

        return argsdict['text']

    return COLOR_REGEX.sub(single_sub, escape(text))

def create_ws(app):
    socketio = SocketIO(app)

    def follow(filename, last_pos, sid):
        print 'SocketIO: starting loop for ' + sid
        try:
            hub = gevent.get_hub()
            watcher = hub.loop.stat(str(filename))

            # Loop until the WebSocket client has disconnected
            while sid in socketio.server.rooms(sid):
                # Read all lines from log file, beginning at last_pos
                lines = []
                new_pos = 0
                with open(filename) as f:
                    f.seek(last_pos)
                    for line in f:
                        lines.append(ansi_to_html(line).replace('\n', '<br>'))
                    new_pos = f.tell()

                # Send new data to WebSocket client, if any
                if new_pos != last_pos:
                    data = {
                            'html': ''.join(lines),
                            'last_pos': last_pos,
                            }
                    socketio.emit('job', data, room=sid)
                    print 'SocketIO: sent data for ' + sid

                # Update last_pos for next iteration
                last_pos = new_pos

                # Wait until the log file is modified or a 60 seconds timeout elapses 
                try:
                    with gevent.Timeout(60):
                        hub.wait(watcher)
                except gevent.Timeout:
                    continue
        except IOError:
            data = {
                    'html': 'ERROR: failed to read log file.',
                    'last_pos': 0,
                    }
            socketio.emit('job', data, room=sid)
        print 'SocketIO: ending loop for ' + sid

    @socketio.on('connect')
    def handle_connect():
        print 'SocketIO: connected from ' + request.sid

    @socketio.on('disconnect')
    def handle_disconnect():
        print 'SocketIO: disconnected from ' + request.sid

    @socketio.on('job_logging')
    def handle_message(data):
        print 'SocketIO: request from ' + request.sid
        if data and data.get('log_id'):
            log_id = data.get('log_id')
            last_pos = data.get('last_pos', 0)
            filename = LOG_ROOT + '/' + log_id + '.txt'

            # Spawn the follow loop in another thread to end this request and avoid CLOSED_WAIT connections leaking
            gevent.spawn(follow, filename, last_pos, request.sid)
        else:
            data = {
                'html': 'No log file yet.',
                'last_pos': 0,
                }
            socketio.emit('job', data, room=request.sid)

    return socketio
