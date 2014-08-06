#!/bin/bash
#
# Buid the s3cfg file with the IAM role credentials attach to this isntance.
# use s3cmd --config /tmp/s3cmfg ...
#

# Get credentials
IAM=$(curl http://169.254.169.254/latest/meta-data/iam/info 2>/dev/null | grep InstanceProfileArn | awk -F"/" '{print $2}'| tr -d '"|,')
export AWS_ACCESS_KEY_ID=$(curl http://169.254.169.254/latest/meta-data/iam/security-credentials/${IAM} 2> /dev/null | grep AccessKeyId | awk '{print $3}' | tr -d '"|,')
export AWS_SECRET_ACCESS_KEY=$(curl http://169.254.169.254/latest/meta-data/iam/security-credentials/${IAM} 2> /dev/null |  grep SecretAccessKey | awk '{print $3}' | tr -d '"|,')
export AWS_SESSION_TOKEN=$(curl http://169.254.169.254/latest/meta-data/iam/security-credentials/${IAM} 2>/dev/null |  grep Token | awk '{print $3}' | tr -d '"|,')
INSTANCE_ID=$(curl http://169.254.169.254/latest/meta-data/instance-id)
EC2_AVAIL_ZONE=$(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone)
EC2_REGION="`echo \"$EC2_AVAIL_ZONE\" | sed -e 's:\([0-9][0-9]*\)[a-z]*\$:\\1:'`"

TAGS=$(aws ec2 describe-tags --filters "Name=resource-id,Values=$INSTANCE_ID" --region "$EC2_REGION")
NAME=$(echo $TAGS | jq -r ".Tags[] | { key: .Key, value: .Value } | [.] | from_entries" | jq -r '.["Name"] | select (.!=null)')
ROLE=$(echo $TAGS | jq -r ".Tags[] | { key: .Key, value: .Value } | [.] | from_entries" | jq -r '.["Role"] | select (.!=null)')
ENV=$(echo $TAGS | jq -r ".Tags[] | { key: .Key, value: .Value } | [.] | from_entries" | jq -r '.["Env"] | select (.!=null)')
APP=$(echo $TAGS | jq -r ".Tags[] | { key: .Key, value: .Value } | [.] | from_entries" | jq -r '.["App"] | select (.!=null)')

# Build s3cmd credential file
cat >/tmp/s3cfg <<EOM
[default]
access_key = $ACCESS_KEY
secret_key = $SECRET_KEY
security_token = $AWS_SESSION_TOKEN
region = eu-west-1
EOM
mv /tmp/s3cfg ~/.s3cfg


S3_BUCKET=staging.worldsbestbars
s3cmd --force get s3://$S3_BUCKET/MANIFEST /tmp/
[ $? -ne 0 ] && exit 10
PACKAGE=$(head -n 1 /tmp/MANIFEST)
rm /tmp/MANIFEST
s3cmd --force get s3://$S3_BUCKET/$PACKAGE /tmp/
[ $? -ne 0 ] && exit 10
IFS='_' read -a array <<< "$PACKAGE"
TIMESTAMP=${array[0]}
sudo mkdir -p /ghost/$TIMESTAMP
sudo chown -R admin /ghost
tar xvzf /tmp/$PACKAGE -C /ghost/$TIMESTAMP
rm /tmp/$PACKAGE
sudo chown -R www-data:www-data /ghost/$TIMESTAMP
sudo rm /var/www
sudo ln -s /ghost/$TIMESTAMP /var/www
sudo service apache2 restart
