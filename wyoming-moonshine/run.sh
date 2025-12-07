#!/usr/bin/env sh
set -e

# Persist Hugging Face cache under /data so models are reused across restarts
export HF_HOME=/data/huggingface
export HUGGINGFACE_HUB_CACHE="${HF_HOME}/hub"
mkdir -p "${HUGGINGFACE_HUB_CACHE}"

OPTIONS_FILE="/data/options.json"

MODEL=$(jq -r '.model // "moonshine/tiny"' "$OPTIONS_FILE")
LANGUAGE=$(jq -r '.language // "en"' "$OPTIONS_FILE")
LOG_LEVEL=$(jq -r '.log_level // "INFO"' "$OPTIONS_FILE")

echo "Starting wyoming_moonshine with model=${MODEL}, language=${LANGUAGE}, log_level=${LOG_LEVEL}"

exec python3 -m wyoming_moonshine \
  --uri tcp://0.0.0.0:10300 \
  --model "${MODEL}" \
  --language "${LANGUAGE}" \
  --log-level "${LOG_LEVEL}"
