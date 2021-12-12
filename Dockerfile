FROM debian:10

LABEL maintainer="dmintz"

RUN apt-get update
RUN apt-get install -y python3 python3-dev python3-pip nginx
RUN pip3 install uwsgi

COPY ./requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt

# We copy just the requirements.txt first to leverage Docker cache
COPY ./ /app
WORKDIR /app

RUN pip3 install -r requirements.txt

ENV WEBROOT='/'
ENV TZ='UTC'

EXPOSE 80
CMD [ "uwsgi", "--ini", "/app/espn-scoreboard.ini" ]