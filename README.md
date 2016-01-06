# Requirements

## Dev
Installing requirements:

    $ pip install -r requirements.txt

Updating dependencies:

    $ pip-compile -U
    $ pip-sync

Running unit tests with tox (sets up a virtualenv under the hood):

    $ tox

Running unit tests directly (dependencies should be provided by the system or an active virtualenv):

    $ ./run_tests.py

# Deployment

## docker-compose

    $ export AWS_ACCESS_KEY_ID=AKIAI*******
    $ export AWS_SECRET_ACCESS_KEY=********************
    $ docker-compose build
    $ docker-compose up

## Sur instance EC2:
* utiliser morea-salt-formulas
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
* utiliser morea-salt-formulas

# Configuration:
## accounts:
* copy accounts.yml.dist as accounts.yml
* add account with 'python auth.py user password'
* restart ghost process

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

# Ghost config.yml
    ses_settings:
        aws_access_key: XXXXXXXXXXXXXXXXXX
        aws_secret_key: XXXXXXXXXXXXXXXXXX
        region: eu-west-1
    bucket_s3: ghost.env.example.com.1234567890
    key_path: /home/admin/key.pem
    salt_formulas_branch: dev
    ghost_root_path: /usr/local/share/ghost
    jobs_kept: 42

jobs_kept define how many s3 pckages to keep

# Updating AWS data
Requires curl, nodejs and jq:

    (echo 'function callback(data) { console.log(JSON.stringify(data)); }'; curl -s 'http://a0.awsstatic.com/pricing/1/ec2/linux-od.min.js') | nodejs | jq -r '.config.regions' > aws_data_instance_types.json
