
CONFIG_LLM = configs/llm.yaml

# Check if yq is installed
YQ_CMD := $(shell command -v yq)
ifndef YQ_CMD
$(error "yq is not installed. Please install yq to proceed.")
endif

# Extract variables from configs/llm.yaml
MODEL_NAME := $(shell $(YQ_CMD) e '.llm.model' $(CONFIG_LLM))
PROMPT_SYSTEM := $(shell $(YQ_CMD) e '.llm.prompt_system' $(CONFIG_LLM))
TEMPERATURE := $(shell $(YQ_CMD) e '.llm.temperature' $(CONFIG_LLM))

.PHONY: run

run:
	@echo "Using Model Name: $(MODEL_NAME)"
	@echo "Using Prompt System: $(PROMPT_SYSTEM)"
	@echo "Using Temperature: $(TEMPERATURE)"
	# Export environment variables and run docker compose
	MODEL_NAME='$(MODEL_NAME)' \
	PROMPT_SYSTEM='$(PROMPT_SYSTEM)' \
	TEMPERATURE='$(TEMPERATURE)' \
	docker compose up -d --build

stop:
	@echo "Stopping all containers"
	docker compose down