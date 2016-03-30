class ACloudConnection(object):
    """
    Abstract to establish connection to a cloud service provider
    the **kwags option is used here as an attribute of the class
    to make it more flaxible and allow the user to whatever is needed
    for the cloud connection 
    """
    
    def __init__(self, log_file, **kwargs):
        self._log_file = log_file
        self._parameters = kwargs

    def get_connection(self, region, service):
        """
        method to be implemented by all class inheriting from this class
        """
        print self._log_file
        print self._parameters

