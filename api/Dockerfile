FROM python:3.11

RUN groupadd -r web && useradd -r -g web web

WORKDIR /code

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y \
    netcat-traditional \
    wget \
    tzdata \
    perl \
    libgeo-gpx-perl \
    libxml-libxml-perl \
    libclone-perl \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Europe/Moscow
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get update
RUN apt-get install -y gettext

COPY ./api/requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r ./requirements.txt

COPY ./api/entrypoint.sh /web/entrypoint.sh
RUN chmod +x /web/entrypoint.sh

COPY rubicon_admin/ .
COPY tg_bot/ /code/tg_bot/

RUN mkdir -p static
RUN mkdir -p /code/media/map_layers
RUN chmod -R 755 /code/media
RUN mkdir -p /code/static/videos
RUN chmod -R 755 /code/static/videos

RUN mkdir -p /code/staticfiles
RUN chmod -R 755 /code/staticfiles

RUN mkdir -p /code/logs
RUN chmod 777 /code/logs

RUN chmod -R 755 /code
RUN chmod 777 /code/static

# USER web


ENTRYPOINT ["/web/entrypoint.sh"]