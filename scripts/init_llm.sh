#!/usr/bin/env bash

# This script is used to initialize the LLM environment
apt-get update
apt-get install curl -y

ollama serve &
ollama list
curl -X POST http://ollama:11434/api/pull -d '{"name": "qwen2.5:7b"}'
curl -X POST http://ollama:11434/api/run -d '{"name": "qwen2.5:7b"}'
tail -f /dev/null