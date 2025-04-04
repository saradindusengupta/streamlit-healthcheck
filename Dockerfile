FROM python:3.9-slim
COPY requirements.txt requirements.txt
COPY src/ /src/
COPY config/ /config/
RUN ls /src
RUN ls /config

WORKDIR /src

RUN apt-get update && apt-get install -y \
    build-essential \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install -U -r requirements.txt
RUN python -m build