FROM python:3.12-slim AS app_server

# Install Poetry
RUN pip install poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache
WORKDIR /app
# Copy the dependencies files
COPY ./work.duchungtech.com.key ./
COPY ./work.duchungtech.com.crt ./
COPY pyproject.toml ./
COPY ./Qwen-Agent ./Qwen-Agent
RUN poetry install --no-root

COPY configs ./configs
RUN poetry install

ENTRYPOINT ["poetry", "run", "python", "-m", "botvov.main"]
EXPOSE 5000


FROM ollama/ollama:latest AS ollama
WORKDIR /app
COPY ./scripts/init_llm.sh ./
RUN chmod +x init_llm.sh
ENTRYPOINT ["./init_llm.sh"]


FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04 AS speech2text
# `ffmpeg` is installed because without it `gradio` won't work with mp3(possible others as well) files
# hadolint ignore=DL3008,DL3015,DL4006
RUN apt-get update && \
    apt-get install -y ffmpeg software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3.12 python3-pip python3.12-distutils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.4.4 /uv /bin/uv
WORKDIR /root/faster-whisper-server
# https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=./speech2text/uv.lock,target=uv.lock \
    --mount=type=bind,source=./speech2text/pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project
COPY ./speech2text/src ./speech2text/pyproject.toml ./
COPY ./speech2text/uv.lock ./
COPY ./models ./models
COPY ./scripts/ct2_converter.sh ./
RUN chmod +x ct2_converter.sh
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen
ENV WHISPER__MODEL=./models/PhoWhisper-small-ct2
ENV WHISPER__INFERENCE_DEVICE=auto
ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=9000
# CMD ["uv", "run", "uvicorn", "faster_whisper_server.main:app"]


FROM pytorch/pytorch:1.13.1-cuda11.6-cudnn8-runtime AS text2speech
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY .env /app/.env
COPY ./configs /app/configs
COPY ./models/text2speech/ /app/models/
COPY ./text2speech/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY text2speech /app/text2speech

ENTRYPOINT [ "python", "-m", "text2speech.main" ]