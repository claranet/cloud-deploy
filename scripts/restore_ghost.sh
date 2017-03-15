#!/bin/bash

set -e

# We must be root
if [ "$EUID" -ne 0 ]
  then echo "Please run this script as root (or with sudo)"
  exit 1
fi

LOG_FILE=/var/log/ghost/ghost-restore.log
GHOST_LOGS=/var/log/ghost
mkdir -pv $GHOST_LOGS
# Redirect stdout ( > ) into a named pipe ( >() ) running "tee"
exec > >(tee -i $LOG_FILE)
exec 2>&1

# Args check
if [ $# -lt 2 ] || [ $# -gt 3 ]; then
    echo "Invalid args."
    echo "Usage: $0 {s3_ghost_bucket} {s3_bucket_region} [backup_file_name]"
    echo
    echo "[backup_file_name] is optional, if not specified the script will retrieve the latest backup (more recent) from S3"
    echo
    echo "Example: $0 's3.support.ghost-packages.eu-west-1' 'eu-west-1'"
    echo "Example: $0 's3.support.ghost-packages.eu-west-1' 'eu-west-1' 'ghost-backup-2016-01-19_13_19.tar.gz'"
    exit 1
fi

# Variables
S3=$1
S3_REGION=$2
RESTORE=/tmp/restore_ghost
GHOST_HOME=/usr/local/share/ghost

if [ -z "$3" ]; then
    # Check and get lastest backup from S3 bucket
    LATEST_BACKUP_INFOS=$(/usr/local/bin/aws s3 ls s3://$S3/backup/ --region $S3_REGION | tail -n1)
    if [ -z "$LATEST_BACKUP_INFOS" ]; then
        echo "No backup found in s3://$S3/backup/. Please verify arguments"
        exit 2
    fi
    echo "Backup found: $LATEST_BACKUP_INFOS"
    LATEST_BACKUP=$(echo $LATEST_BACKUP_INFOS | tr -s ' ' | cut -d' ' -f4)
else
    LATEST_BACKUP=$3
    echo "Backup filename specified, trying to restore: $LATEST_BACKUP"
fi

# Create restore dir
mkdir -pv $RESTORE
cd $RESTORE

# Get and unpack backup archive
/usr/local/bin/aws s3 cp --region $S3_REGION s3://$S3/backup/$LATEST_BACKUP ./$LATEST_BACKUP
tar xvf $LATEST_BACKUP
cd ./tmp/backup_ghost/

# Restore Ghost configs
cp -vf ./*.yml $GHOST_HOME/
chown -v ghost. $GHOST_HOME/*.yml
chmod -v 600 $GHOST_HOME/*.yml

# Restore ssh_config files
mkdir -pv $GHOST_HOME/.ssh
cp -vf ./ssh_config $GHOST_HOME/.ssh/config
chown -R ghost. $GHOST_HOME/.ssh/
chmod -v 700 $GHOST_HOME/.ssh/
chmod -v 644 $GHOST_HOME/.ssh/config

# Restore Ghost logs
cp -rvf ./logs/*.txt $GHOST_LOGS/
chown -R ghost. $GHOST_LOGS/

# Restore MongoDB
mongorestore dump

# Restart Ghost services
supervisorctl restart ghost
supervisorctl restart rqworker
supervisorctl restart front

# Infos
grep -Hni "key" ./config.yml
grep -Hni ".pem" ./config.yml
echo "Don't forget to deploy those SSH private key(s)"
echo "Don't forget to install specifics system pkgs needed by applications'"

# Cleanup
rm -rf $RESTORE

exit 0
