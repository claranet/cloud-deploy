# Dockerfile used by docker-compose to run Ghost

FROM moreaghost/morea-ghost:2017.11.30

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt
