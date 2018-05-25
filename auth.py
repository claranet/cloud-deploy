try:
    import bcrypt
    import yaml
    from eve.auth import BasicAuth
    from notification import Notification, MAIL_LOG_FROM_DEFAULT, TEMPLATES_DIR
    import requests
    from jinja2 import Environment, FileSystemLoader
except ImportError as e:
    print('Needed pip modules not found. Please make sure your virtualenv is \
           activated and pip requirements well installed.')
    raise

import argparse
import os

ACCOUNTS_FILE = 'accounts.yml'
ONE_TIME_SECRET_URL = 'https://onetimesecret.com/api/v1/share'


class BCryptAuth(BasicAuth):
    _accounts = {
        'api': '$2a$12$HHKaH4pKaz1iiv2lmqQXmuF1./zWsFIDphpU9JXOFHRrBIkhbF.si'}

    def __init__(self):
        read_accounts(self._accounts)

    def check_auth(self, username, password, allowed_roles, resource, method):
        stored_password = self._accounts.get(username, None)

        return (stored_password and
                bcrypt.hashpw(password, stored_password) == stored_password)


def load_conf(user, password, email):
    rootdir = os.path.dirname(os.path.realpath(__file__))
    conf_file_path = rootdir + '/config.yml'
    conf_file = open(conf_file_path, 'r')
    conf = yaml.load(conf_file)

    conf['account'] = {}
    conf['account']['user'] = user
    conf['account']['password'] = password
    conf['account']['email'] = email

    return conf


def generate_one_time_secret(conf):
    try:
        ots_settings = conf['one_time_secret']
        r = requests.post(ONE_TIME_SECRET_URL,
                          auth=(ots_settings['username'],
                                ots_settings['api_key']),
                          params={'secret': conf['account']['password'],
                                  'ttl': ots_settings['ttl'],
                                  'passphrase': ots_settings['passphrase']})
        if r.status_code != 200:
            raise r.raise_for_status()
        
        ots_settings['secret_key'] = r.json()['secret_key']

    except (requests.ConnectionError, requests.HTTPError) as e:
        print("couldn't generate one time secret: " + str(e))


def format_html(conf):
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template('account_creation_template.html.j2')
    html_body = template.render(
        username=conf['account']['user'],
        secret_key=conf['one_time_secret']['secret_key'],
        ghost_url=(conf['ghost_base_url'] if 'http' in conf['ghost_base_url']
                   else 'https://' + conf['ghost_base_url']),
        ttl=conf['one_time_secret']['ttl'] / 3600,
        passphrase=conf['one_time_secret']['passphrase'],
    )

    return html_body


def send_mail(conf):
    ses_settings = conf['ses_settings']
    notif = Notification(aws_access_key=ses_settings['aws_access_key'],
                         aws_secret_key=ses_settings['aws_secret_key'],
                         region=ses_settings['region'])
    
    try:
        notif.send_mail(From=ses_settings.get('mail_from', MAIL_LOG_FROM_DEFAULT),
                        To=conf['account']['email'],
                        subject="Cloud Deploy account created",
                        body_html=format_html(conf))

    except Exception as e:
        print("couldn't send email confirmation: " + str(e))


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

    if args.user and args.password:
        # Load existing accounts
        accounts = {}
        read_accounts(accounts)

        # Add account
        accounts[args.user] = bcrypt.hashpw(args.password, bcrypt.gensalt())

        # Save accounts
        with open(ACCOUNTS_FILE, 'w') as accounts_file:
            yaml.dump(accounts, accounts_file)

        # Send email
        if args.email:
            conf = load_conf(args.user, args.password, args.email)
            generate_one_time_secret(conf)
            send_mail(conf)


if __name__ == '__main__':
    main()
