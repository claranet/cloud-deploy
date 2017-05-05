import os

from flask import request
from flask_socketio import SocketIO
import gevent
import re
from xml.sax.saxutils import escape
import os.path

from settings import cloud_connections, DEFAULT_PROVIDER
from ghost_tools import config, get_job_log_remote_path
from ghost_aws import download_file_from_s3

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
LOG_LINE_REGEX = re.compile(r'\d+/\d+/\d+ \d+:\d+:\d+ .*: .*')

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
                readlines = []
                lines = []
                new_pos = 0
                eof = False

                with open(filename) as f:
                    # Read maximum 1000 lines from log file at a time, beginning at last_pos
                    f.seek(last_pos)
                    readlines = f.readlines(1000)
                    # Capture new_pos
                    new_pos = f.tell()
                    # Check if we already are at end of file
                    f.seek(0, os.SEEK_END)
                    eof = f.tell() == new_pos

                    # Decorate lines
                    for idx, line in enumerate(readlines):
                        for sub_line in line.split("\\n"):
                            clean_line = ansi_to_html(sub_line).replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br/>').replace('%!(PACKER_COMMA)', '&#44;')
                            if LOG_LINE_REGEX.match(sub_line) is not None:
                                lines.append('%s<div class="panel panel-default"><em class="panel-heading"><span class="timeinterval"><i class="glyphicon glyphicon-time"></i></span><span class="command-title">%s</span></em><div class="panel-body">'
                                    % ('</div></div>' if idx > 0 else '', clean_line))
                            else:
                                lines.append('<samp>%s</samp>' % clean_line)

                # Send new data to WebSocket client, if any
                if new_pos != last_pos:
                    data = {
                        'html': ''.join(lines),
                        'last_pos': last_pos,
                    }
                    socketio.emit('job', data, room=sid)

                # Update last_pos for next iteration
                last_pos = new_pos

                # If at end of file, wait until the log file is modified or a timeout elapses
                if eof:
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
            # FIXME: this is a vulnerability as a malicious user may pass '../' in log_id to read other files on the filesystem
            filename = LOG_ROOT + '/' + log_id + '.txt'
            if not os.path.isfile(filename):
                cloud_connection = cloud_connections.get(DEFAULT_PROVIDER)(None)
                bucket_name = config['bucket_s3']
                region = config.get('bucket_region', 'eu-west-1')

                remote_log_path = get_job_log_remote_path(log_id)
                download_file_from_s3(cloud_connection, bucket_name, region, remote_log_path, filename)

            # Spawn the follow loop in another thread to end this request and avoid CLOSED_WAIT connections leaking
            gevent.spawn(follow, filename, last_pos, request.sid)
        else:
            data = {
                'html': 'No log file yet.',
                'last_pos': 0,
            }
            socketio.emit('job', data, room=request.sid)

    return socketio
