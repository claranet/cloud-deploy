# Dockerfile used by docker-compose to run Ghost

FROM 845945358136.dkr.ecr.eu-west-1.amazonaws.com/cloud-deploy-ci:2018-05-14

COPY requirements.txt requirements.txt

USER root

RUN pip install -r requirements.txt

USER ghost
