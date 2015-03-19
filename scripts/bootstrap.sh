#!/bin/bash
set -x
S3_BUCKET={{ bucket_s3 }}
TS=$(date +%Y%m%H%m%S)
LOGFILE=$(echo $TS"_deploy.txt")

INSTANCE_ID=$(curl http://169.254.169.254/latest/meta-data/instance-id)
EC2_AVAIL_ZONE=$(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone)
EC2_REGION="`echo \"$EC2_AVAIL_ZONE\" | sed -e 's:\([0-9][0-9]*\)[a-z]*\$:\\1:'`"

TAGS=$(/usr/local/bin/aws ec2 describe-tags --filters "Name=resource-id,Values=$INSTANCE_ID" --region "$EC2_REGION")
NAME=$(echo $TAGS | jq -r ".Tags[] | { key: .Key, value: .Value } | [.] | from_entries" | jq -r '.["Name"] | select (.!=null)')
ROLE=$(echo $TAGS | jq -r ".Tags[] | { key: .Key, value: .Value } | [.] | from_entries" | jq -r '.["role"] | select (.!=null)')
ENV=$(echo $TAGS | jq -r ".Tags[] | { key: .Key, value: .Value } | [.] | from_entries" | jq -r '.["env"] | select (.!=null)')
APP=$(echo $TAGS | jq -r ".Tags[] | { key: .Key, value: .Value } | [.] | from_entries" | jq -r '.["app"] | select (.!=null)')

if [ -d /ghost ]; then
    chown -R admin /ghost
else
    mkdir /ghost && chown -R admin.admin /ghost
fi
function deploy_module() {
    echo "--------------------------------" >> /tmp/$LOGFILE
    echo "Deploying module $1 in $3" >> /tmp/$LOGFILE
    /usr/local/bin/aws s3 cp s3://$S3_BUCKET/ghost/$APP/$ENV/$ROLE/$1/$2 /tmp/$2  --region "$EC2_REGION"
    mkdir -p /ghost/$2
    echo "Extracting module in /ghost/$2" >> /tmp/$LOGFILE
    tar xvzf /tmp/$2 -C /ghost/$2 > /dev/null
    rm -rf $3
    ln -s /ghost/$2 $3
    cd $3
    if [ -e postdeploy ]
    then
        echo "Executing postdeploy script..." >> /tmp/$LOGFILE
        chmod +x postdeploy
        ./postdeploy
    fi
}
function find_module() {
    for line in $(cat /tmp/MANIFEST)
      do
        MODULE_NAME=$(echo $line | awk -F':' '{print $1}')
        MODULE_TAR=$(echo $line | awk -F':' '{print $2}')
        MODULE_PATH=$(echo $line | awk -F':' '{print $3}')
	    if [ "$1" == "$MODULE_NAME" ]; then
            deploy_module $MODULE_NAME $MODULE_TAR $MODULE_PATH
        fi
    done
}

function exit_deployment() {
    echo "Removing Manifest file" >> /tmp/$LOGFILE
    rm /tmp/MANIFEST
    exit $1
}

echo "Downloading Manifest" >> /tmp/$LOGFILE
/usr/local/bin/aws s3 cp s3://$S3_BUCKET/ghost/$APP/$ENV/$ROLE/MANIFEST /tmp/ --region "$EC2_REGION"
if [ $? -ne 0 ]; then
    echo "Manifest download error...Exiting" >> /tmp/$LOGFILE
    exit_deployment 10
fi
# Deploy only one module
if [ -n "$1" ]; then
    MODULE=$(find_module $1)
    deploy_module $MODULE
    exit_deployment 0
fi
# Deploying all modules
for line in $(cat /tmp/MANIFEST)
do
    MODULE_NAME=$(echo $line | awk -F':' '{print $1}')
    MODULE_TAR=$(echo $line | awk -F':' '{print $2}')
    MODULE_PATH=$(echo $line | awk -F':' '{print $3}')
    deploy_module $MODULE_NAME $MODULE_TAR $MODULE_PATH
done
