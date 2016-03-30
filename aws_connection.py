import boto  
from ghost_tools import log
from boto.sts import STSConnection 
from cloud_connection import ACloudConnection


class AWSConnection(ACloudConnection):
   
    def __init__(self, log_file,**kwargs):
        super(AWSConnection, self).__init__(log_file, **kwargs)
        assumed_account_id = self._parameters.get('assumed_account_id', None)
        if (assumed_account_id):
            self._role_arn = "arn:aws:iam::" + assumed_account_id + ":role/"
            self._role_arn = self._parameters.get('assumed_role', None)
            self._role_session = "ghost_aws_cross_account"
        else:
            self._role_arn = None

    def get_connection(self, region, service):
        connection = None
        try:
            aws_service = getattr(boto, service)
            if not self._role_arn:
                connection = aws_service.connect_to_region(region)
            else:
                sts_connection = STSConnection()
                assumed_role = sts_connection.assume_role(
                        role_arn=self._role_arn,
                        role_session_name=self._role_session
                )
                access_key = assumed_role_object.credentials.access_key
                secret_key = assumed_role_object.credentials.secret_key
                session_token = assumed_role_object.credentials.session_token
                connection = aws_service.connect_to_region(
                        region,
                        aws_access_key_id=access_key,
                        aws_secret_access_key=secret_key,
                        security_token=session_token
                )
        except:
            log("An error occured when creating connection, check the exception error message for more details", self._log_file)
            raise
        return (connection)
