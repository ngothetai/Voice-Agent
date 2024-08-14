FROM python:3.12-slim AS app_server
# Install Poetry
RUN pip install poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache
WORKDIR /app

# Copy the dependencies files
COPY pyproject.toml ./
RUN poetry install --no-root

COPY botvov ./botvov
RUN poetry install

ENTRYPOINT ["poetry", "run", "python", "-m", "botvov.run_server"]
EXPOSE 7860


FROM ollama/ollama:latest AS ollama
WORKDIR /app
COPY init_llm.sh ./
ENTRYPOINT ["./init_llm.sh"]