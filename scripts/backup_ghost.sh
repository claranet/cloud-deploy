#!/bin/bash

#requirements
# TODO

SCRIPTPATH=$( cd $(dirname $0) ; pwd -P )
CONFIG="$SCRIPTPATH/../config.yml"
if [ $# -eq 1 ]; then
    S3_REGION=$1
elif [ ! -z "$(grep bucket_region $CONFIG )" ]; then
    S3_REGION=`grep bucket_region $CONFIG | cut -d' ' -f2`
else
    S3_REGION='eu-west-1'
fi

BACKUP=/tmp/backup_ghost
FILE="ghost-backup-`date +"%F_%H_%M"`.tar.gz"
sudo mkdir $BACKUP
cd $BACKUP
sudo mongodump
sudo cp /home/admin/ghost/*.yml .
sudo mkdir logs
sudo cp -r /var/log/ghost* logs/
cd ..

sudo tar zcf $FILE $BACKUP
S3=`grep bucket_s3 $CONFIG | cut -d' ' -f2`
/usr/local/bin/aws s3 cp $FILE --region $S3_REGION s3://$S3/backup/
sudo rm -rf $BACKUP
sudo rm -rf $FILE
