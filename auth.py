import sys
import bcrypt
from eve.auth import BasicAuth

class BCryptAuth(BasicAuth):

    _accounts = { 'api': 'api' }

    def check_auth(self, username, password, allowed_roles, resource, method):
        # use Eve's own db driver; no additional connections/resources are used
        stored_password = self._accounts[username]

        #return account and bcrypt.hashpw(password, account['pass']) == account['pass']
        return stored_password == password

