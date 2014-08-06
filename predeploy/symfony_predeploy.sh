php composer.phar update
php composer.phar install --prefer-source --no-interaction
php app/console doctrine:schema:update --force
php app/console assets:install web --symlink
php app/console assets:install web --symlink --env=prod
php app/console assetic:dump
php app/console assetic:dump --env=prod
php app/console cache:clear
php app/console cache:clear --env=prod
