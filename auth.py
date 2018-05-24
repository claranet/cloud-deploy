try:
    import bcrypt
    import yaml
    from eve.auth import BasicAuth
    from notification import Notification, MAIL_LOG_FROM_DEFAULT
except ImportError as e:
    print 'Needed pip modules not found. Please make sure your virtualenv is \
           activated and pip requirements well installed.'
    raise

import argparse
import os

ACCOUNTS_FILE = 'accounts.yml'


class BCryptAuth(BasicAuth):
    _accounts = {
        'api': '$2a$12$HHKaH4pKaz1iiv2lmqQXmuF1./zWsFIDphpU9JXOFHRrBIkhbF.si'}

    def __init__(self):
        read_accounts(self._accounts)

    def check_auth(self, username, password, allowed_roles, resource, method):
        stored_password = self._accounts.get(username, None)

        return (stored_password and
                bcrypt.hashpw(password, stored_password) == stored_password)


def load_ses_conf():
    rootdir = os.path.dirname(os.path.realpath(__file__))
    conf_file_path = rootdir + "/config.yml"
    conf_file = open(conf_file_path, 'r')
    conf = yaml.load(conf_file)
    ses_conf = conf['ses_settings']

    return ses_conf


def send_mail(conf, mail):
    notif = Notification(aws_access_key=conf['aws_access_key'],
                         aws_secret_key=conf['aws_secret_key'],
                         region=conf['region'])
    
    notif.send_mail(From=conf.get('mail_from', MAIL_LOG_FROM_DEFAULT),
                    To=mail,
                    subject="test",
                    body_text="body",
                    body_html="test")


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
    parser.add_argument('email')
    return parser.parse_args()


def main():
    args = parse_args()

    # Send email
    if args.email:
        conf = load_ses_conf()
        send_mail(conf, args.email)
        exit(0)

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
