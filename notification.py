from boto import ses
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
import ntpath

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

