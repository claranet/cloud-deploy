# Dockerfile used by docker-compose to run Ghost

FROM moreaghost/morea-ghost:2017.11.30-5

COPY requirements.txt requirements.txt

USER root

RUN pip install -r requirements.txt

USER ghost
