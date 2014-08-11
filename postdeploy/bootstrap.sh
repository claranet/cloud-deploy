#!/bin/bash
#
# use s3cmd --config /tmp/s3cmfg ...
#
S3_BUCKET=deploy-811874869762

# Get credentials
# IAM=$(curl http://169.254.169.254/latest/meta-data/iam/info 2>/dev/null | grep InstanceProfileArn | awk -F"/" '{print $2}'| tr -d '"|,')
# export AWS_ACCESS_KEY_ID=$(curl http://169.254.169.254/latest/meta-data/iam/security-credentials/${IAM} 2> /dev/null | grep AccessKeyId | awk '{print $3}' | tr -d '"|,')
# export AWS_SECRET_ACCESS_KEY=$(curl http://169.254.169.254/latest/meta-data/iam/security-credentials/${IAM} 2> /dev/null |  grep SecretAccessKey | awk '{print $3}' | tr -d '"|,')
# export AWS_SESSION_TOKEN=$(curl http://169.254.169.254/latest/meta-data/iam/security-credentials/${IAM} 2>/dev/null |  grep Token | awk '{print $3}' | tr -d '"|,')
INSTANCE_ID=$(curl http://169.254.169.254/latest/meta-data/instance-id)
EC2_AVAIL_ZONE=$(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone)
EC2_REGION="`echo \"$EC2_AVAIL_ZONE\" | sed -e 's:\([0-9][0-9]*\)[a-z]*\$:\\1:'`"

TAGS=$(/usr/local/bin/aws ec2 describe-tags --filters "Name=resource-id,Values=$INSTANCE_ID" --region "$EC2_REGION")
NAME=$(echo $TAGS | jq -r ".Tags[] | { key: .Key, value: .Value } | [.] | from_entries" | jq -r '.["Name"] | select (.!=null)')
ROLE=$(echo $TAGS | jq -r ".Tags[] | { key: .Key, value: .Value } | [.] | from_entries" | jq -r '.["Role"] | select (.!=null)')
ENV=$(echo $TAGS | jq -r ".Tags[] | { key: .Key, value: .Value } | [.] | from_entries" | jq -r '.["Env"] | select (.!=null)')
APP=$(echo $TAGS | jq -r ".Tags[] | { key: .Key, value: .Value } | [.] | from_entries" | jq -r '.["App"] | select (.!=null)')

# Build s3cmd credential file
cat > ~/.s3cfg <<EOM
[default]
access_key =
secret_key =
security_token =
region = $EC2_REGION
EOM

s3cmd --force get s3://$S3_BUCKET/$APP/$ENV/$ROLE/MANIFEST /tmp/
[ $? -ne 0 ] && exit 10
PACKAGE=$(head -n 1 /tmp/MANIFEST)
rm /tmp/MANIFEST
s3cmd --force get s3://$S3_BUCKET/$APP/$ENV/$ROLE/$PACKAGE /tmp/
[ $? -ne 0 ] && exit 10
IFS='_' read -a array <<< "$PACKAGE"
TIMESTAMP=${array[0]}
mkdir -p /ghost/$TIMESTAMP
chown -R admin /ghost
echo "Extracting $PACKAGE..."
tar xvzf /tmp/$PACKAGE -C /ghost/$TIMESTAMP > /dev/null
rm /tmp/$PACKAGE
chown -R www-data:www-data /ghost/$TIMESTAMP
rm /var/www
ln -s /ghost/$TIMESTAMP /var/www
service apache2 restart
