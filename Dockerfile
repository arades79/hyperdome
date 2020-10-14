FROM python:3.8-alpine

ENV $POETRY_VERSION=1.0.10

RUN pip install --upgrade pip
RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /code

COPY pyproject.toml poetry.lock