# Claranet Cloud Deploy

- Documentation: [https://docs.cloud-deploy.io/](https://docs.cloud-deploy.io/)
- Related repositories: [Claranet Github](https://github.com/claranet?utf8=%E2%9C%93&q=cloud-deploy&type=&language=)
- Cloud Deploy CLI: [Casper](https://github.com/claranet/casper)

![Cloud Deploy](https://www.cloudeploy.io/ghost/full_logo.png)

Cloud Deploy (Ghost Project) aims to deploy applications in the Cloud, in a secure and reliable way. Actual version support only AWS.

Key features:

- Developed in Python.
- Designed for continuous deployment.
- Create, configure and update AWS EC2 instances.
- Used to deploy client application code
- Cloud Deploy core build within a REST API that any REST client could use it
- A Web User Interface, available only for Claranet customers or with Enterprise license
- [Casper](https://docs.cloud-deploy.io/rst/cli.html#cli): CLI client

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

Compatible with Debian.

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

### On an AWS EC2 instance:

* Ask Claranet who can provide VM image or Ansible/SaltStack playbook and formula.

## Configuration:
### Accounts:
* copy accounts.yml.dist as accounts.yml
* add account with `python auth.py user password`
* restart `ghost` (API/Core) process to reload accounts

## Example data
    JOB
    {
        command: "deploy",
        parameters: [options: "hard", app_id: APPLICATION_ID, modules: [name: "php5", rev: "staging"]],
        status: "launched"
    }

    APP
    {
***REMOVED***
***REMOVED***
***REMOVED***
        ],
        "env": "staging",
        "features": [{"name": "php5-fpm", "version": "5.5"}, {"name": "nginx", "version": "1.4.2"], // version optionnel, name = SaltStack state
        "role" : "webserver",
***REMOVED***
        "log_notifications" : [
            "ingenieurs@morea.fr",
            "wbb-notification@void.fr"
        ],
        "ami": "ami_id", // Stored by Packer
        "instance_type": "t2.small"
        "autoscale": {"min": 1, "max": 2, "current": 1}
    }

## Updating AWS data
Requires curl, nodejs and jq:

    (echo 'function callback(data) { console.log(JSON.stringify(data)); }'; curl -s 'http://a0.awsstatic.com/pricing/1/ec2/linux-od.min.js') | nodejs | jq -r '.config.regions' > aws_data_instance_types.json
    (echo 'function callback(data) { console.log(JSON.stringify(data)); }'; curl -s 'https://a0.awsstatic.com/pricing/1/ec2/previous-generation/linux-od.min.js') | nodejs | jq -r '.config.regions' > aws_data_instance_types_previous.json
