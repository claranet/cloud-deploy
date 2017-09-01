FROM moreaghost/morea-ghost:2017.09.01-2

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt
