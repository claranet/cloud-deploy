# Claranet Cloud Deploy 
[![Documentation](https://img.shields.io/badge/documentation-cloud--deploy-brightgreen.svg)](https://docs.cloud-deploy.io) [![CLI](https://img.shields.io/badge/cli-casper-blue.svg)](https://github.com/claranet/casper) [![API Reference](http://img.shields.io/badge/api-reference-blue.svg)](https://docs.cloud-deploy.io/rst/api.html) [![Changelog](https://img.shields.io/badge/changelog-release-green.svg)](https://docs.cloud-deploy.io/rst/changelog.html) [![Apache V2 License](http://img.shields.io/badge/license-Apache%20V2-blue.svg)](https://github.com/claranet/cloud-deploy/blob/stable/LICENSE)

- Documentation: [https://docs.cloud-deploy.io/](https://docs.cloud-deploy.io/)
- Related repositories: [Claranet Github](https://github.com/claranet?utf8=%E2%9C%93&q=cloud-deploy&type=&language=)
- Cloud Deploy CLI: [Casper](https://github.com/claranet/casper)

![Cloud Deploy](https://www.cloudeploy.io/ghost/full_logo.png)

Cloud Deploy (Ghost Project) aims to deploy applications in the Cloud, in a secure and reliable way. Current version supports only AWS.

Key features:

- Developed in Python.
- Designed for continuous deployment.
- Create, configure and update AWS EC2 instances.
- Used to deploy customer application code.
- Cloud Deploy core is built with a REST API that any REST client can use.
- A Web User Interface, available only for Claranet customers or with Enterprise license.
- [Casper](https://docs.cloud-deploy.io/rst/cli.html#cli): CLI client.

## Requirements

### Python:
* virtualenv
* pip >= 9.0.1 (in local virtualenv)
* pip-tools >= 1.9.0 (in local virtualenv)

### Packages:
* MongoDB
* Redis
* Supervisor
* Nginx

### Dependencies and tools
* Cloud Deploy uses [Packer](https://www.packer.io/) to bake VM images
* Compatible with [SaltStack](https://saltstack.com/) and [Ansible](https://www.ansible.com/) to provision requirements in VM images
* Uses [Fabric](http://www.fabfile.org/) for SSH connections and live deployment

## Development

Installing requirements:

    $ pip install -r requirements.txt

Updating dependencies:

    $ pip-compile
    $ pip install -r requirements.txt

Upgrading dependencies:

    $ pip-compile -U
    $ pip install -r requirements.txt

Running unit tests with tox (sets up a virtualenv under the hood):

    $ tox

Running unit tests directly (dependencies should be provided by the system or an active virtualenv):

    $ ./run_tests.py

## Deployment

### Locally via docker-compose:

    $ export AWS_ACCESS_KEY_ID=AKIAI*******
    $ export AWS_SECRET_ACCESS_KEY=********************
    $ docker-compose build
    $ docker-compose up

## Configuration:
### Accounts:
* copy accounts.yml.dist as accounts.yml
* add account with `python auth.py <user> <password>`. You can also use the `-e <email>` option to specify an email address that will receive account's creation confirmation.
* restart `ghost` (API/Core) process to reload accounts
