#!/bin/bash

# Close STDOUT file descriptor
exec 1<&-
# Close STDERR FD
exec 2<&-

# Open STDOUT as $LOG_FILE file for read and write.
LOG_FILE=/var/log/ghost/ghost-backup.log
exec 1<>$LOG_FILE

# Redirect STDERR to STDOUT
exec 2>&1

# Variables
SCRIPTPATH=$( cd $(dirname $0) ; pwd -P )
CONFIG="$SCRIPTPATH/../config.yml"
S3=$(grep bucket_s3 $CONFIG | cut -d' ' -f2)
S3_REGION=$(grep bucket_region $CONFIG | cut -d' ' -f2)
BACKUP=/tmp/backup_ghost
FILE="ghost-backup-`date +"%F_%H_%M"`.tar.gz"

if [ $# -eq 1 ]; then
    S3_REGION=$1
elif [ -z "$S3_REGION" ]; then
    S3_REGION='eu-west-1'
fi

# Create backup dir
mkdir $BACKUP
cd $BACKUP

# Dump mongodb
mongodump

# Copy configuration
cp $SCRIPTPATH/../*.yml .
cp -f $SCRIPTPATH/../.ssh/config ./ssh_config

# Copy jobs' logs
mkdir logs
cp -r /var/log/ghost/*.txt logs/

# Copy nginx config
mkdir nginx
cp /etc/nginx/sites-enabled/* ./nginx

# Copy supervisor config
mkdir supervisor
cp /etc/supervisor/conf.d/* ./supervisor

# Create archive
cd ..
tar -czf $FILE $BACKUP

# Upload archive to S3
/usr/local/bin/aws s3 cp $FILE --region $S3_REGION s3://$S3/backup/

# Cleanup
rm -rf $BACKUP
rm -f $FILE
