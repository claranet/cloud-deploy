from boto import ses
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

from ghost_log import log

import ntpath
import requests
import json

class Notification():
    _aws_access_key = None
    _aws_secret_key = None
    _region = None

    def __init__(self, aws_access_key=None, aws_secret_key=None, region=None):
        self._aws_access_key = aws_access_key
        self._aws_secret_key = aws_secret_key
        self._region = region

    def send_mail(self, From="", To="", subject="", body="", attachments=[]):
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = From
        msg['To'] = To
        msg.preamble = 'Multipart message.\n'
        # the message body
        part = MIMEText(body)
        msg.attach(part)
        # the attachment
        for attachment in attachments:
            part = MIMEApplication(open(attachment, 'rb').read())
            part.add_header('Content-Disposition', 'attachment', filename=ntpath.basename(attachment))
            msg.attach(part)
        # connect to SES
        connection = ses.connect_to_region(self._region, aws_access_key_id=self._aws_access_key, aws_secret_access_key=self._aws_secret_key)
        # and send the message
        result = connection.send_raw_email(msg.as_string(), source=msg['From'], destinations=[msg['To']])
        return(result)

    def send_slack_notification(self, config, msg, log_file=None):
        try:
            slack_url = config.get('webhooks_endpoint')
            notif = "{prefix}{msg}".format(prefix=config.get('message_prefix', ''), msg=msg)
            payload = {
                "channel": config.get('channel', '#ghost-deployments'),
                "username": config.get('bot_name', 'Ghost-bot'),
                "text": notif,
                "icon_emoji": config.get('bot_icon', ':ghost:')
            }
            r = requests.post(slack_url, json.dumps(payload), headers={'content-type': 'application/json'})
            if log_file:
                log("Slack post status : {0} - {1}".format(r.status_code, r.text), log_file)
        except Exception as e:
            if log_file:
                log("Error sending notification to Slack (%s)" % str(e), log_file)
