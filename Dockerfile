FROM python:3.12-slim as base
# Install Poetry
RUN pip install -U pip setuptools
RUN pip install poetry
WORKDIR /app
COPY . .
# Install dependencies
RUN poetry install
EXPOSE 7860
