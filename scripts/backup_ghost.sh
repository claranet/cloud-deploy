#!/bin/bash

#requirements
# TODO

BACKUP=/tmp/backup_ghost
FILE="ghost-backup-`date +"%F_%H_%M"`.tar.gz"
sudo mkdir $BACKUP
cd $BACKUP
sudo mongodump
sudo cp /home/admin/ghost/*.yml .
sudo mkdir logs
sudo cp -r /var/log/ghost* logs
cd ..

sudo tar zcf $FILE $BACKUP
S3=`grep bucket_s3 /home/admin/ghost/config.yml | cut -d' ' -f2`
aws s3 cp $FILE --region eu-west-1  s3://$S3/backup/
sudo rm -rf $BACKUP
sudo rm -rf $FILE
