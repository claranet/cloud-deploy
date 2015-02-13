import bcrypt
from eve.auth import BasicAuth

class BCryptAuth(BasicAuth):

    _accounts = [
        {'user':'api','pass':'api'}
        ]

    def check_auth(self, username, password, allowed_roles, resource, method):
        # use Eve's own db driver; no additional connections/resources are used
        account = (item for item in self._accounts if item["user"] == username).next()
        #return account and bcrypt.hashpw(password, account['pass']) == account['pass']
        return account and password == account['pass']

