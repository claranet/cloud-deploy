# Requirements

## Dev
Installing requirements:
    $ pip install -r requirements.txt

Checking for updates:
    $ pip-sync

Running unit tests:
    $ python -m doctest -v web_ui/*.py
    $ python -m doctest -v worker.py

# Deployment

## Sur instance2:
* jq (transformation JSON en ligne de commande)
* python pip boto awscli
* s3cmd (prendre version GitHub sinon cela ne fonctionne pas)
* Role IAM avec Policy :
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": [
            "s3:Get*",
            "s3:List*",
            "ec2:DescribeTags"
          ],
          "Resource": "*"
        }
      ]
    }

## Sur bastion:
* python pip boto awscli
* les dépendances sur les scripts predeploy (ex: php5 avec memcached, gd...)
* mongodb
* les packages contenus dans requirements.txt

# Configuration:
## accounts:
* copy accounts.yml.dist as accounts.yml
* add account with 'python auth.py user password'
* restart ghost process

## notifications:
* db.config.insert({ "ses_settings": {"aws_access_key": "SES_AWS_ACCESS_KEY", "aws_secret_key": "SES_AWS_SECRET_KEY", "region": "eu-west-1"}})

# Notes
* Necessite une version de Fabric >= 1.10.1 (Bug encoding fixed)

# Example data
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

# Updating AWS data
Requires curl, nodejs and jq:

    (echo 'function callback(data) { console.log(JSON.stringify(data)); }'; curl -s 'http://a0.awsstatic.com/pricing/1/ec2/linux-od.min.js') | nodejs | jq -r '.config.regions' > aws_data_instance_types.json
