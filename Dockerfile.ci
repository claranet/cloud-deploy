# Dockerfile used to build cloud-deploy-ci image for bitbucket pipeline
# The main Dockerfile is also based on it.
# Refer to https://confluence.fr.clara.net/display/MOR/Updating+the+docker+image+used+by+automated+unit+tests+execution for instructions

FROM python:2.7

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get -y -q update && \
    apt-get -y -q install unzip

RUN wget https://releases.hashicorp.com/packer/1.2.1/packer_1.2.1_linux_amd64.zip && \
    unzip -d /usr/local/bin packer_1.2.1_linux_amd64.zip && \
    rm packer_1.2.1_linux_amd64.zip

RUN pip install tox

RUN adduser --disabled-password --gecos "" --home /usr/local/share/ghost ghost

RUN mkdir -p /ghost /var/log/ghost /var/lib/ghost

RUN chown ghost:ghost /ghost /var/log/ghost /var/lib/ghost

USER ghost
