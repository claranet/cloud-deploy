import argparse
import bcrypt
import os
import yaml
from eve.auth import BasicAuth

ACCOUNTS_FILE = 'accounts.yml'

class BCryptAuth(BasicAuth):
    _accounts = { 'api': '$2a$12$HHKaH4pKaz1iiv2lmqQXmuF1./zWsFIDphpU9JXOFHRrBIkhbF.si' }

    def __init__(self):
        read_accounts(self._accounts)

    def check_auth(self, username, password, allowed_roles, resource, method):
        stored_password = self._accounts[username]

        return stored_password and bcrypt.hashpw(password, stored_password) == stored_password


def read_accounts(accounts):
    if os.path.isfile(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE) as accounts_file:
            accounts.clear()
            accounts.update(yaml.load(accounts_file))


def parse_args():
    parser = argparse.ArgumentParser(
        description='Adds user account to accounts.yml.'
    )
    parser.add_argument('user')
    parser.add_argument('password')
    return parser.parse_args()


def main():
    args = parse_args()

    if args.user and args.password:
        # Load existing accounts
        accounts = {}
        read_accounts(accounts)

        # Add account
        accounts[args.user] = bcrypt.hashpw(args.password, bcrypt.gensalt())

        # Save accounts
        with open(ACCOUNTS_FILE, 'w') as accounts_file:
            yaml.dump(accounts, accounts_file)

if __name__ == '__main__':
    main()
