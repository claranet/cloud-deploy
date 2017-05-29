from boto import ses
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

from ghost_log import log
from ghost_tools import GHOST_JOB_STATUSES_COLORS

import requests
import json

import os
from gzip import GzipFile
import shutil
import StringIO

class Notification():
    _aws_access_key = None
    _aws_secret_key = None
    _region = None

    def __init__(self, aws_access_key=None, aws_secret_key=None, region=None):
        self._aws_access_key = aws_access_key
        self._aws_secret_key = aws_secret_key
        self._region = region

    def send_mail(self, From="", To="", subject="", body_text="", body_html="", attachments=[]):
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = From
        msg['To'] = To
        msg.preamble = 'Multipart message.\n'
        # the message body
        # part1 = MIMEText(body_text, 'plain')
        part2 = MIMEText(body_html, 'html')
        msg.attach(part2)
        # msg.attach(part1)
        # the attachment
        for attachment in attachments:
            log_path = attachment['original_log_path']
            with open(log_path, 'rb') as f_in:
                log_stat = os.stat(log_path)
                if log_stat.st_size > 512000:
                    gz_data = StringIO.StringIO()
                    with GzipFile(fileobj=gz_data, mode='wb', compresslevel=9, filename=attachment['filename']) as gz_out:
                        shutil.copyfileobj(f_in, gz_out)
                    part = MIMEApplication(gz_data.getvalue())
                    part.add_header('Content-Disposition', 'attachment', filename=attachment['filename']+'.gz')
                    gz_data.close()
                else:
                    part = MIMEApplication(f_in.read())
                    part.add_header('Content-Disposition', 'attachment', filename=attachment['filename'])
                msg.attach(part)

        # connect to SES
        connection = ses.connect_to_region(self._region, aws_access_key_id=self._aws_access_key, aws_secret_access_key=self._aws_secret_key)
        # and send the message
        result = connection.send_raw_email(msg.as_string(), source=msg['From'], destinations=[msg['To']])
        return(result)

    def send_slack_notification(self, config, msg, app, job, job_log, log_file=None):
        try:
            slack_url = config.get('webhooks_endpoint')
            if config.get('ghost_base_url'):
                notif = "[<{ghost_url}|{prefix}>]{msg} <{ghost_url}/web/jobs/{jobId}|{jobId}>".format(
                    ghost_url=config['ghost_base_url'],
                    prefix=config.get('message_prefix', 'Ghost'),
                    msg=msg,
                    jobId=str(job['_id']))
            else:
                notif = "[{prefix}]{msg}".format(prefix=config.get('message_prefix', 'Ghost'), msg=msg)
            fields = [
                {
                    "title": "Application",
                    "value": app['name'],
                    "short": True
                },
                {
                    "title": "Environnement",
                    "value": app['env'],
                    "short": True
                },
                {
                    "title": "Role",
                    "value": app['role'],
                    "short": True
                },
                {
                    "title": "Command",
                    "value": job['command'],
                    "short": True
                },
                {
                    "title": "User",
                    "value": job['user'],
                    "short": True
                },
                {
                    "title": "Status",
                    "value": job['status'],
                    "short": True
                },
                {
                    "title": "Message",
                    "value": job['message'],
                    "short": False
                },
                {
                    "title": "Log extract",
                    "value": job_log,
                    "short": False
                }
            ]

            payload = {
                "channel": config.get('channel', '#ghost-deployments'),
                "username": config.get('bot_name', 'Claranet Cloud Deploy'),
                "icon_url": config.get('bot_icon', 'https://www.cloudeploy.io/ghost/cloud_deploy_logo_128.png'),
                "attachments": [
                {
                    "fallback": notif,
                    "pretext": config.get('message_prefix', 'Ghost job triggered'),
                    "color": GHOST_JOB_STATUSES_COLORS[job['status']],
                    "fields": fields,
                    "title": "Job #{jobId} triggered by {user}".format(jobId=str(job['_id']), user=job['user']),
                    "title_link": "{ghost_url}/web/jobs/{jobId}".format(ghost_url=config['ghost_base_url'], jobId=str(job['_id'])),
                    "footer": "Created at {created}".format(created=job['_created']),
                }]
            }
            r = requests.post(slack_url, json.dumps(payload), headers={'content-type': 'application/json'})
            if log_file:
                log("Slack post status : {0} - {1}".format(r.status_code, r.text), log_file)
        except Exception as e:
            if log_file:
                log("Error sending notification to Slack (%s)" % str(e), log_file)
