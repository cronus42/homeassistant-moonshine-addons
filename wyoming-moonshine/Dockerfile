ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

# Install Python and tools needed for pip + options parsing
RUN apk add --no-cache python3 py3-pip git jq

WORKDIR /app

# Python dependencies
COPY requirements.txt ./
RUN python3 -m venv "${VIRTUAL_ENV}" \
    && "${VIRTUAL_ENV}/bin/pip" install --upgrade pip \
    && "${VIRTUAL_ENV}/bin/pip" install -r requirements.txt

# Application code
COPY wyoming_moonshine ./wyoming_moonshine
COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 10300

CMD ["/run.sh"]
