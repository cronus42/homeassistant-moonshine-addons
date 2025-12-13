#!/usr/bin/env sh
set -e

OPTIONS_FILE="/data/options.json"

MODEL=$(jq -r '.model // "moonshine/tiny"' "$OPTIONS_FILE")
LANGUAGE=$(jq -r '.language // "en"' "$OPTIONS_FILE")
LOG_LEVEL=$(jq -r '.log_level // "INFO"' "$OPTIONS_FILE")

# If true, we allow Hugging Face access only during startup to populate the cache,
# then force offline for the remainder of the process.
OFFLINE_AFTER_STARTUP=$(jq -r '.offline_after_startup // true' "$OPTIONS_FILE")
HF_HOME_DIR=$(jq -r '.hf_home_dir // "/data/hf"' "$OPTIONS_FILE")

export HF_HOME="${HF_HOME_DIR}"
mkdir -p "${HF_HOME}"

HF_TOKEN_VALUE=$(jq -r '.hf_token // empty' "$OPTIONS_FILE")
if [ -n "${HF_TOKEN_VALUE}" ]; then
  export HF_TOKEN="${HF_TOKEN_VALUE}"
else
  unset HF_TOKEN
fi

# Used by the warmup snippet.
export MODEL

echo "Starting wyoming_moonshine with model=${MODEL}, language=${LANGUAGE}, log_level=${LOG_LEVEL}, offline_after_startup=${OFFLINE_AFTER_STARTUP}, hf_home=${HF_HOME}"

if [ "${OFFLINE_AFTER_STARTUP}" = "true" ]; then
  echo "Warming model cache (network allowed during startup only)"

  # Ensure we are not in offline mode during warmup.
  unset HF_HUB_OFFLINE
  unset TRANSFORMERS_OFFLINE

  # Trigger model artifact download into the HF cache.
  # This also runs one short inference, which is acceptable at startup.
  if command -v timeout >/dev/null 2>&1; then
    timeout 300 python3 - <<'PY'
import os
import tempfile
import wave
from pathlib import Path

import moonshine_onnx

model = os.environ["MODEL"]

# Create a tiny 16kHz/16-bit mono WAV of silence.
fd, wav_path_str = tempfile.mkstemp(suffix=".wav")
os.close(fd)

wav_path = Path(wav_path_str)
with wave.open(str(wav_path), "wb") as wav_file:
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(16000)
    wav_file.writeframes(b"\x00\x00" * 16000)  # 1 second

try:
    moonshine_onnx.transcribe(wav_path, model)
finally:
    try:
        wav_path.unlink()
    except FileNotFoundError:
        pass
PY
  else
    echo "WARNING: timeout(1) not found; warmup may hang if network is broken"
    python3 - <<'PY'
import os
import tempfile
import wave
from pathlib import Path

import moonshine_onnx

model = os.environ["MODEL"]

# Create a tiny 16kHz/16-bit mono WAV of silence.
fd, wav_path_str = tempfile.mkstemp(suffix=".wav")
os.close(fd)

wav_path = Path(wav_path_str)
with wave.open(str(wav_path), "wb") as wav_file:
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(16000)
    wav_file.writeframes(b"\x00\x00" * 16000)  # 1 second

try:
    moonshine_onnx.transcribe(wav_path, model)
finally:
    try:
        wav_path.unlink()
    except FileNotFoundError:
        pass
PY
  fi

  echo "Enabling Hugging Face offline mode for the running server"
  export HF_HUB_OFFLINE=1
  export TRANSFORMERS_OFFLINE=1
fi

exec python3 -m wyoming_moonshine \
  --uri tcp://0.0.0.0:10300 \
  --model "${MODEL}" \
  --language "${LANGUAGE}" \
  --log-level "${LOG_LEVEL}"
