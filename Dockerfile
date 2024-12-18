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
RUN poetry install --no-root
RUN poetry add loguru "burr[tracking-client,tracking-server,streamlit,graphviz,hamilton]"

COPY configs ./configs
RUN poetry install

COPY botvov ./botvov

EXPOSE 5000 5001

RUN chmod +x botvov/run_burr_UI.sh

CMD ["sh", "./botvov/run_burr_UI.sh"]

# ENTRYPOINT ["poetry", "run", "python", "-m", "botvov.main"]


FROM vllm/vllm-openai AS llm_serve
WORKDIR /serve
ARG MODEL_NAME
ENV MODEL_NAME=$MODEL_NAME
ENV HUGGING_FACE_HUB_TOKEN=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
ENV CUDA_DEVICE_ORDER=PCI_BUS_ID
ENV NCCL_DEBUG=INFO
ENTRYPOINT python3 -m vllm.entrypoints.openai.api_server --host 0.0.0.0 --port 8000 --model $MODEL_NAME --gpu_memory_utilization 0.8 --tensor-parallel-size 2 --enable-auto-tool-choice --tool-call-parser hermes

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
ENV WHISPER__MODEL=./models/PhoWhisper-large-ct2
ENV WHISPER__INFERENCE_DEVICE=auto
ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=9000
# CMD ["uv", "run", "uvicorn", "faster_whisper_server.main:app"]


FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime AS text2speech
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# COPY .env /app/.env
COPY ./configs/text2speech /app/configs/text2speech
COPY ./models/text2speech/ /app/models/
COPY ./text2speech/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY text2speech /app/text2speech

ENV CONFIG_FILE=configs/text2speech/config.json
ENV PHONE_SET_FILE=configs/text2speech/phone_set.json
ENV DURATION_MODEL=models/duration_model.pth
ENV LIGHTSPEED_MODEL_PATH=models/gen_630k.pth

ENTRYPOINT [ "python", "-m", "text2speech.main" ]