FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV HF_HOME=/data/huggingface \
    HUGGINGFACE_HUB_CACHE=/data/huggingface/hub

# System dependencies needed for pip (git+https URLs) and run.sh (jq for /data/options.json)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       git \
       jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt ./
RUN python -m venv "${VIRTUAL_ENV}" \
    && "${VIRTUAL_ENV}/bin/pip" install --upgrade pip \
    && "${VIRTUAL_ENV}/bin/pip" install -r requirements.txt

# Application code
COPY wyoming_moonshine ./wyoming_moonshine
COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 10300

CMD ["/run.sh"]
