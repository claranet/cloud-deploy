import boto
from boto import vpc, iam
from boto.ec2 import autoscale
from boto.sts import STSConnection 
from cloud_connection import ACloudConnection

from ghost_log import log

class AWSConnection(ACloudConnection):
   
    def __init__(self, log_file=None, **kwargs):
        super(AWSConnection, self).__init__(log_file, **kwargs)
        assumed_account_id = self._parameters.get('assumed_account_id', None)
        if (assumed_account_id):
            self._role_arn = "arn:aws:iam::" + assumed_account_id + ":role/"
            self._role_arn += self._parameters.get('assumed_role_name', '')
            self._role_session = "ghost_aws_cross_account"
        else:
            self._role_arn = None

    def _get_boto_service(self, boto_obj, attributes):
        """
        Recursive help function to build the boto connection hierarchy
        the order of services list is important and should be like this:
        ['ec2'], ['ec2', 'autoscale'], [s3], ['ec2', 'elb'] and not like
        this : ['autoscale', 'ec2'], ['s3', 'ec2']. Check the GHOST API
        documentation for more informations
        """
        if attributes:
            if len(attributes) == 1:
                return(getattr(boto_obj, attributes[0]))
            return(self._get_boto_service(getattr(boto_obj, attributes[0]), attributes[1:]))

    def check_credentials(self):
        result = False
        if not self._role_arn:
            result = True
        else:
            try:
                sts_connection = STSConnection()
                assumed_role_object = sts_connection.assume_role(
                        role_arn=self._role_arn,
                        role_session_name=self._role_session
                )
                self._parameters['access_key'] = assumed_role_object.credentials.access_key
                self._parameters['secret_key'] = assumed_role_object.credentials.secret_key
                self._parameters['session_token'] = assumed_role_object.credentials.session_token
                result = True
            except:
                if self._log_file:
                    log("An error occured when creating connection, check the exception error message for more details", self._log_file)
                result = False
                raise
        return (result)

    def get_credentials(self):
        credentials = {
                'aws_access_key': None,
                'aws_secret_key': None,
                'token': None
        }
        if self._role_arn:
            try:
                self.check_credentials()
                credentials['aws_access_key'] = self._parameters['access_key']
                credentials['aws_secret_key'] = self._parameters['secret_key']
                credentials['token'] = self._parameters['session_token']
            except:
                if self._log_file:
                    log("An error occured when creating connection, check the exception error message for more details", self._log_file)
                raise
        return(credentials)


        print self._parameters

    def get_connection(self, region, services):
        connection = None
        try:
            aws_service = self._get_boto_service(boto, services)
            if not self._role_arn:
                connection = aws_service.connect_to_region(region)
            elif self.check_credentials():
                connection = aws_service.connect_to_region(
                        region,
                        aws_access_key_id=self._parameters['access_key'],
                        aws_secret_access_key=self._parameters['secret_key'],
                        security_token=self._parameters['session_token']
                )
        except:
            if self._log_file:
                log("An error occured when creating connection, check the exception error message for more details", self._log_file)
            raise
        return (connection)

    def get_regions(self, services):
        regions = None
        try:
            aws_service = self._get_boto_service(boto, services)
            if not self._role_arn:
                regions = aws_service.regions()
            elif self.check_credentials():
                regions = aws_service.regions(
                        aws_access_key_id=self._parameters['access_key'],
                        aws_secret_access_key=self._parameters['secret_key'],
                        security_token=self._parameters['session_token']
                )
        except:
            if self._log_file:
                log("An error occured when creating connection, check the exception error message for more details", self._log_file)
            raise
        return (regions)

    def launch_service(self, services, *args, **kwargs):
        service = None
        try:
            aws_service = self._get_boto_service(boto, services)
            service = aws_service(*args, **kwargs)
        except:
            if self._log_file:
                log("An error occured when creating connection, check the exception error message for more details", self._log_file)
            raise
        return (service)
