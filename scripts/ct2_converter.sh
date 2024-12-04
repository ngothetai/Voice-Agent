MODEL_DIR="./models/PhoWhisper-large-ct2"

if [ ! -d "$MODEL_DIR" ]; then
    pip install ctranslate2 transformers[torch]
    mkdir -p "$MODEL_DIR"
    ct2-transformers-converter --model vinai/PhoWhisper-large --quantization bfloat16 --output_dir "$MODEL_DIR" --force
fi
echo "Model is ready at $MODEL_DIR"