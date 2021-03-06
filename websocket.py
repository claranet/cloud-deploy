# -*- coding: utf-8 -*-

import base64
import chardet
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
from ghost_blueprints import get_websocket_token

LOG_ROOT = '/var/log/ghost'

COLOR_DICT = {
    '31': [(255, 0, 0), (128, 0, 0)],
    '32': [(0, 255, 0), (0, 128, 0)],
    '33': [(255, 255, 0), (128, 128, 0)],
    '34': [(0, 175, 255), (0, 0, 128)],
    '35': [(255, 0, 255), (128, 0, 128)],
    '36': [(0, 255, 255), (0, 128, 128)],
}

COLOR_REGEX = re.compile(r'(\^\[|\033)\[(?P<arg_1>\d+)(;(?P<arg_2>\d+)(;(?P<arg_3>\d+))?)?m(?P<text>.*?)(?=\^\[|\033|$)')
LOG_LINE_REGEX = re.compile(r'\d+/\d+/\d+ \d+:\d+:\d+ .*: .*')

BOLD_TEMPLATE = '<span style="color: rgb{}; font-weight: bolder">{}</span>'
LIGHT_TEMPLATE = '<span style="color: rgb{}">{}</span>'


class HtmlLogFormatter():
    @staticmethod
    def format_line(log_line, line_number):
        """
        Format a log line to HTML format.
        :param log_line: str:
        :param line_number: int:
        :return: str:

        >>> HtmlLogFormatter.format_line('log line', 0)
        '<samp>log line</samp>'

        >>> HtmlLogFormatter.format_line('2018/02/08 16:34:44 GMT: Job processing started', 0)
        '<div class="panel panel-default"><em class="panel-heading"><span class="timeinterval"><i class="glyphicon glyphicon-time"></i></span><span class="command-title">2018/02/08 16:34:44 GMT: Job processing started</span></em><div class="panel-body">'

        >>> HtmlLogFormatter.format_line('2018/02/08 16:34:44 GMT: Job processing started', 1)
        '</div></div><div class="panel panel-default"><em class="panel-heading"><span class="timeinterval"><i class="glyphicon glyphicon-time"></i></span><span class="command-title">2018/02/08 16:34:44 GMT: Job processing started</span></em><div class="panel-body">'
        """
        clean_line = ansi_to_html(log_line).replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br/>').replace('%!(PACKER_COMMA)', '&#44;')
        if LOG_LINE_REGEX.match(log_line) is not None:
            return '%s<div class="panel panel-default"><em class="panel-heading"><span class="timeinterval"><i class="glyphicon glyphicon-time"></i></span><span class="command-title">%s</span></em><div class="panel-body">' % ('</div></div>' if line_number > 0 else '', clean_line)
        else:
            return '<samp>%s</samp>' % clean_line

    @staticmethod
    def format_data(lines, last_pos):
        """
        Format a websocket data to HTML format.
        :param lines: array: An array containing log lines
        :param last_pos: int: Last file position
        :return: dict:

        >>> sorted(HtmlLogFormatter.format_data(["line1", "line2"], 10).items())
        [('html', 'line1line2'), ('last_pos', 10)]

        >>> sorted(HtmlLogFormatter.format_data([], 0).items())
        [('html', ''), ('last_pos', 0)]
        """
        return {'html': ''.join(lines), 'last_pos': last_pos}

    @staticmethod
    def format_error(error_message):
        """
        Format a websocket error to HTML format.
        :param error_message: str:
        :return: dict:

        >>> sorted(HtmlLogFormatter.format_error('Test error').items())
        [('html', '<div class="panel panel-default"><em class="panel-heading"><span class="timeinterval"><i class="glyphicon glyphicon-time"></i></span><span class="command-title"><span style="color: #f44336">ERROR: Test error</span></span></em><div class="panel-body"></div></div>'), ('last_pos', 0)]

        >>> sorted(HtmlLogFormatter.format_error('').items())
        [('html', '<div class="panel panel-default"><em class="panel-heading"><span class="timeinterval"><i class="glyphicon glyphicon-time"></i></span><span class="command-title"><span style="color: #f44336">ERROR: </span></span></em><div class="panel-body"></div></div>'), ('last_pos', 0)]

        >>> sorted(HtmlLogFormatter.format_error(None).items())
        [('html', '<div class="panel panel-default"><em class="panel-heading"><span class="timeinterval"><i class="glyphicon glyphicon-time"></i></span><span class="command-title"><span style="color: #f44336">ERROR: </span></span></em><div class="panel-body"></div></div>'), ('last_pos', 0)]
        """
        return {'html': '<div class="panel panel-default"><em class="panel-heading"><span class="timeinterval"><i class="glyphicon glyphicon-time"></i></span><span class="command-title"><span style="color: #f44336">ERROR: {}</span></span></em><div class="panel-body"></div></div>'.format(error_message if error_message else ''), 'last_pos': 0}


class RawLogFormatter():
    @staticmethod
    def format_line(log_line, line_number):
        """
        Format a log line to RAW format.
        :param log_line: str:
        :param line_number: int:
        :return: str:

        >>> RawLogFormatter.format_line('log line', 0)
        'log line'

        >>> RawLogFormatter.format_line('2018/02/08 16:34:44 GMT: Job processing started', 0)
        '2018/02/08 16:34:44 GMT: Job processing started'

        >>> RawLogFormatter.format_line('2018/02/08 16:34:44 GMT: Job processing started', 1)
        '2018/02/08 16:34:44 GMT: Job processing started'
        """
        return log_line

    @staticmethod
    def format_data(lines, last_pos):
        """
        Format a websocket data to RAW format.
        :param lines: array: An array containing log lines
        :param last_pos: int: Last file position
        :return: dict:

        >>> sorted(RawLogFormatter.format_data(["line1", "line2"], 10).items())
        [('last_pos', 10), ('raw', 'bGluZTFsaW5lMg==')]

        >>> sorted(RawLogFormatter.format_data([], 0).items())
        [('last_pos', 0), ('raw', '')]
        """
        return {'raw': base64.b64encode(''.join(lines)), 'last_pos': last_pos}

    @staticmethod
    def format_error(error_message):
        """
        Format a websocket error to RAW format.
        :param error_message: str:
        :return: dict:

        >>> sorted(RawLogFormatter.format_error('Test error').items())
        [('error', 'Test error'), ('last_pos', 0), ('raw', None)]

        >>> sorted(RawLogFormatter.format_error('').items())
        [('error', ''), ('last_pos', 0), ('raw', None)]

        >>> sorted(RawLogFormatter.format_error(None).items())
        [('error', None), ('last_pos', 0), ('raw', None)]
        """
        return {'raw': None, 'error': error_message, 'last_pos': 0}


def check_log_id(log_id):
    """
    Check log_id syntax
    :param log_id: string
    :return SRE_Match object

    >>> check_log_id("5ab13d4673c5787c54a75e1d") is not None
    True

    >>> check_log_id("/etc/test") is not None
    False
    """
    return re.match("^[a-f0-9]{24}$", log_id)


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
    '<span style="color: rgb(0, 175, 255)">Some blue text</span>'

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


def encode_line(line):
    """
    Encode any log line to utf-8

    >>> import json # We use json dumps to simulate the way socketio build the websocket packet

    >>> json.dumps(encode_line('é ç è ô ü'), separators=(',', ':'))
    '"\\\\u00e9 \\\\u00e7 \\\\u00e8 \\\\u00f4 \\\\u00fc"'

    >>> json.dumps(encode_line(''), separators=(',', ':'))
    '""'

    >>> json.dumps(encode_line('云部署很酷'), separators=(',', ':'))
    '"\\\\u4e91\\\\u90e8\\\\u7f72\\\\u5f88\\\\u9177"'

    >>> json.dumps(encode_line('(づ｡◕‿‿◕｡)づ'), separators=(',', ':'))
    '"(\\\\u3065\\\\uff61\\\\u25d5\\\\u203f\\\\u203f\\\\u25d5\\\\uff61)\\\\u3065"'

    >>> json.dumps(encode_line('String'), separators=(',', ':'))
    '"String"'
    """

    encoding = chardet.detect(line)
    if encoding['encoding'] == 'utf-8':
        return line
    elif encoding['encoding'] is not None:
        line = line.decode(encoding['encoding']).encode('utf-8')
    else:
        line = line.encode('utf-8')

    return line


def create_ws(app):
    socketio = SocketIO(app)

    def follow(filename, last_pos, sid, formatter):
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
                    for line_number, line in enumerate(readlines):
                        line = encode_line(line)
                        for sub_line in line.split("\\n"):
                            lines.append(formatter.format_line(sub_line, line_number))

                # Send new data to WebSocket client, if any
                if new_pos != last_pos:
                    data = formatter.format_data(lines, last_pos)
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
            socketio.emit('job', formatter.format_error('Failed to read log file.'), room=sid)
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
        formatter = HtmlLogFormatter if data.get('raw_mode') is not True else RawLogFormatter
        if data and data.get('auth_token'):
            if data.get('log_id'):
                log_id = data.get('log_id')
                last_pos = data.get('last_pos', 0)

                if get_websocket_token(log_id) != data.get('auth_token'):
                    socketio.emit('job', formatter.format_error('Invalid authentication token.'), room=request.sid)
                    return

                if check_log_id(log_id) is None:
                    socketio.emit('job', formatter.format_error('Invalid log_id syntax.'), room=request.sid)
                else:
                    filename = os.path.join(LOG_ROOT, log_id + '.txt')
                    if not os.path.isfile(filename):
                        remote_log_path = get_job_log_remote_path(log_id)
                        download_file_from_s3(cloud_connections.get(DEFAULT_PROVIDER)(None), config['bucket_s3'],
                                              config['bucket_region'], remote_log_path, filename)
                    if not os.path.isfile(filename):
                        socketio.emit('job', formatter.format_error('No log file yet.'), room=request.sid)
                        return

                    # Spawn the follow loop in another thread to end this request and avoid CLOSED_WAIT connections leaking
                    gevent.spawn(follow, filename, last_pos, request.sid, formatter)
            else:
                socketio.emit('job', formatter.format_error('Undefined log_id.'), room=request.sid)
        else:
            socketio.emit('job', formatter.format_error('Undefined authentication token.'), room=request.sid)

    return socketio
