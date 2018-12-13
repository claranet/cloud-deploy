#!/bin/bash

set -e

# Close STDOUT file descriptor
exec 1<&-
# Close STDERR FD
exec 2<&-

LOG_FILE=/var/log/ghost/ghost-backup.log

# Truncate log file
> $LOG_FILE

# Open STDOUT as $LOG_FILE file for read and write.
exec 1<>$LOG_FILE

# Redirect STDERR to STDOUT
exec 2>&1

# Variables
SCRIPTPATH=$( cd $(dirname $0) ; pwd -P )
CONFIG="$SCRIPTPATH/../config.yml"
S3=$(grep bucket_s3 $CONFIG | cut -d' ' -f2)
S3_REGION=$(grep bucket_region $CONFIG | cut -d' ' -f2)
BACKUP_DIR=/ghost/.backup_ghost
BACKUP_FILE="ghost-backup-`date +"%F_%H_%M"`.tar.gz"
BACKUP_FILE_PREVIOUS="ghost-backup-previous.tar.gz"

if [ $# -eq 1 ]; then
    S3_REGION=$1
elif [ -z "$S3_REGION" ]; then
    S3_REGION='eu-west-1'
fi

# Cleanup previous execution
rm -rf $BACKUP_DIR
rm -rf $BACKUP_FILE_PREVIOUS

# Create backup dir
mkdir $BACKUP_DIR
cd $BACKUP_DIR

# Dump mongodb
mongodump

# Copy configuration
ln -snf $SCRIPTPATH/../*.yml .
ln -snf $SCRIPTPATH/../.ssh/config ./ssh_config

# Copy jobs' logs
mkdir logs
ln -snf /var/log/ghost/*.txt logs/

# Copy nginx config
mkdir nginx
ln -snf /etc/nginx/sites-enabled/* ./nginx/

# Copy supervisor config
mkdir supervisor
ln -snf /etc/supervisor/conf.d/* ./supervisor/

# Create archive
cd ..
tar --dereference -czf $BACKUP_FILE $BACKUP_DIR

# Upload archive to S3
/usr/local/bin/aws s3 cp --only-show-errors $BACKUP_FILE --region $S3_REGION s3://$S3/backup/

# Rename previous backup file to keep it until next backup
mv -f $BACKUP_FILE $BACKUP_FILE_PREVIOUS
