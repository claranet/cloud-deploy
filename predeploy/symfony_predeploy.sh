#!/bin/sh
# OAuth Token from morea-deploy account used for unattended deployement
ENV=$1
export COMPOSER_HOME="."
cp app/config/parameters_$ENV.yml app/config/parameters.yml
php composer.phar self-update
php composer.phar config -g github-oauth.github.com 891b5b98169ed0c08120fdec90cffaf8c292d7ba
php composer.phar update
php composer.phar install --prefer-source --no-interaction
php app/console doctrine:schema:update --force
php app/console assets:install web
php app/console assets:install web --env=prod
php app/console assetic:dump
php app/console assetic:dump --env=prod
php app/console cache:clear
php app/console cache:clear --env=prod
