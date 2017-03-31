FROM python:2.7

COPY requirements.txt requirements.txt

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get -y -q update && \
    apt-get -y -q install unzip

RUN wget https://releases.hashicorp.com/packer/0.12.2/packer_0.12.2_linux_amd64.zip && \
    unzip -d /usr/local/bin packer_0.12.2_linux_amd64.zip && \
    rm packer_0.12.2_linux_amd64.zip

RUN pip install -r requirements.txt
