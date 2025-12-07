#!/usr/bin/env sh
set -e

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
