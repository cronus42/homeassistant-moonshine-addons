# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Repository overview

This repo contains Home Assistant add-ons. Currently it defines a single add-on, **Wyoming Moonshine ASR**, under `wyoming-moonshine/`. That add-on:
- Runs the Moonshine ONNX speech recognition server
- Exposes it via the Wyoming protocol for Home Assistant voice pipelines
- Is packaged as a Home Assistant add-on with its own Docker image and `config.yaml` manifest

Runtime behavior for the add-on is:
- Home Assistant writes user options into `/data/options.json` inside the container
- `run.sh` reads `model`, `language`, and `log_level` from that JSON using `jq`
- `run.sh` executes `python3 -m wyoming_moonshine` with those values and binds to `tcp://0.0.0.0:10300`
- `wyoming_moonshine.__main__` starts a Wyoming TCP/UNIX server with `AsyncTcpServer`/`AsyncUnixServer` from `wyoming.server`
- Per-connection, a `MoonshineAsrHandler` instance (in `handler.py`) handles the Wyoming ASR protocol:
  - Responds to `describe` with an `info` event describing the ASR program and model
  - Buffers audio between `audio-start` / `audio-chunk` / `audio-stop`
  - Optionally enforces a `max_seconds` limit (via profiles such as `fast-en` and `accurate-en`)
  - Writes the buffered PCM to a temporary WAV file and calls `moonshine_onnx.transcribe`
  - Returns a `Transcript` event with the recognized text (or empty text if audio is too long or empty)

The Python runtime dependencies for the server are defined in `wyoming-moonshine/requirements.txt` and are installed only inside the container image (not in the local dev virtualenv by default).

## Tooling and environment

- Primary language: Python 3.13 (see `PYTHON` default and mypy/ruff config)
- Tooling virtualenv location: `.venv` in the repo root
- Dev tools (installed via `requirements-dev.txt`): `ruff`, `mypy`, `pre-commit`
- Linting and formatting:
  - `ruff` is used for both linting and formatting (configured via `pyproject.toml`)
  - Line length is 88, target version is `py313`
- Type checking:
  - `mypy` is configured for Python 3.13, with strict optional and unused-config/ignore warnings
  - The mypy pre-commit hook is restricted to `wyoming-moonshine/wyoming_moonshine/`
- Pre-commit:
  - `.pre-commit-config.yaml` runs `ruff` (lint + format) and `mypy`

## Common commands

All commands assume you are in the repo root: `homeassistant-moonshine-addons`.

### Environment setup

Create a local virtualenv for **tooling only** (ruff, mypy, pre-commit) — this does **not** install Moonshine runtime dependencies:

```bash path=null start=null
make venv
```

Re-run to ensure the venv and dev tools are present (alias for `venv` target):

```bash path=null start=null
make dev-install
```

> Note: Runtime packages for the ASR server (`wyoming`, `moonshine_onnx`, etc.) are installed in the container from `wyoming-moonshine/requirements.txt`, not via `make venv`.

### Linting and formatting

Run ruff linting on the whole repo:

```bash path=null start=null
make lint
```

Run the ruff formatter:

```bash path=null start=null
make format
```

Run mypy type checking on the Python package:

```bash path=null start=null
make typecheck
```

Install pre-commit hooks (after the venv is created):

```bash path=null start=null
make pre-commit-install
```

Once installed, pre-commit will run ruff and mypy on staged changes.

### Building the Home Assistant add-on image

Build the `wyoming-moonshine` add-on Docker image locally using the Home Assistant base image for amd64:

```bash path=null start=null
make addon-build
```

This runs:
- `cd wyoming-moonshine`
- `docker build` with `--build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest`
- Produces a local image tagged `wyoming-moonshine-addon:local`

The add-on’s Home Assistant manifest is `wyoming-moonshine/config.yaml`, which declares:
- Add-on metadata (name, slug, version, description, architectures)
- Exposed port `10300/tcp`
- User-configurable options: `model`, `language`, `log_level`
- Add-on image naming pattern: `ghcr.io/cronus42/wyoming-moonshine-addon-{arch}`

### Tests

There is currently no test suite or test runner configured in this repo (no `tests/` directory or test-related tooling). If tests are added later, prefer to:
- Add explicit test commands to the `Makefile`
- Keep them documented here for future Warp instances

## Code structure and data flow

High-level layout:

- Repo root
  - `Makefile` — entry point for dev tooling and local add-on builds
  - `pyproject.toml` — ruff and mypy configuration
  - `requirements-dev.txt` — dev-only tooling dependencies
  - `.pre-commit-config.yaml` — pre-commit hooks wiring ruff and mypy
  - `wyoming-moonshine/` — Home Assistant add-on directory
    - `Dockerfile` — container image for the add-on
    - `config.yaml` — Home Assistant add-on manifest and user options schema
    - `requirements.txt` — server runtime dependencies (installed in-container)
    - `run.sh` — entrypoint script used by the container
    - `wyoming_moonshine/` — Python package for the Wyoming ASR server
      - `__init__.py` — exposes `MoonshineAsrHandler`
      - `__main__.py` — CLI entrypoint and server bootstrap
      - `handler.py` — Wyoming ASR event handler implementation

### Wyoming server entrypoint (`wyoming_moonshine.__main__`)

Key responsibilities:
- Parse CLI arguments (`--uri`, `--model`, `--language`, `--log-level`, `--profile`, `--moonshine-option`)
- Apply optional named profiles (`fast-en`, `accurate-en`) that select model, language, and `max_seconds`
  - Explicit `--model` / `--language` flags override profile defaults
- Parse `--moonshine-option KEY=VALUE` pairs into a typed options dict (`_parse_moonshine_options`), coercing values to bool/int/float when possible
- Configure logging (`logging.basicConfig`) based on `--log-level`
- Create a `handler_factory` that instantiates `MoonshineAsrHandler` with:
  - `model_name`
  - `language`
  - optional `max_seconds`
  - `moonshine_options` dict forwarded through to the handler
- Parse `--uri` with `urlparse` and start an appropriate Wyoming server:
  - `tcp://host:port` → `AsyncTcpServer`
  - `unix:///path` → `AsyncUnixServer`

When run as `python -m wyoming_moonshine`, `main()` calls `asyncio.run(_async_main())` to start the server.

### ASR handler (`MoonshineAsrHandler` in `handler.py`)

Responsibilities and flow per connection:
- Extends `AsyncEventHandler` from `wyoming.server`
- Maintains per-connection state:
  - Selected `model_name`, `language`, `max_seconds`
  - Parsed `moonshine_options`
  - Buffered audio bytes and the last `AudioStart` format
  - A flag indicating when audio duration exceeds `max_seconds`

`handle_event` processes incoming Wyoming events:
- `describe` → build and send an `info` event describing the ASR service and currently configured model/language
- `transcribe` → reset internal buffers for a new utterance
- `audio-start` → record audio format (rate/width/channels), clear buffer, and warn if format is not 16kHz/16-bit mono
- `audio-chunk` →
  - Append PCM data to the buffer
  - Track approximate duration; if it exceeds `max_seconds`, mark the utterance as too long and ignore further chunks
- `audio-stop` →
  - If there is no audio or the utterance was too long, immediately send an empty `Transcript` event
  - Otherwise, call `_run_transcription` to perform Moonshine inference and send a `Transcript` event with the recognized text
- Any other event types are logged at debug level and ignored while keeping the connection open

Transcription path:
- `_run_transcription` uses `asyncio.to_thread` to offload the blocking Moonshine ONNX call into a worker thread
- `_transcribe_sync`:
  - Wraps raw PCM into a temporary WAV file (using `wave` and `tempfile`)
  - Calls `moonshine_onnx.transcribe(tmp_path, self.model_name)`
  - Cleans up the temporary file
  - Normalizes the result to a string (handles both list and scalar return types)

### Home Assistant add-on integration

- `wyoming-moonshine/config.yaml` declares the add-on, options, and port mapping
- `wyoming-moonshine/Dockerfile`:
  - Starts from a Home Assistant base image (`BUILD_FROM` arg)
  - Installs Python and tools (`python3`, `py3-pip`, `git`, `jq`)
  - Installs runtime requirements from `requirements.txt`
  - Copies the `wyoming_moonshine` package and `run.sh` into the image and marks `run.sh` executable
  - Exposes port `10300` and sets `CMD ["/run.sh"]`
- `run.sh` acts as the glue between Home Assistant’s options JSON and the Python server process

When modifying the add-on, keep the following relationships in mind:
- If you change CLI flags or defaults in `__main__.py`, ensure `run.sh` (and `config.yaml` options) remain consistent
- If you add new per-model options that should be user-configurable, you will likely need to:
  - Extend `config.yaml` options/schema
  - Update `run.sh` to read them from `/data/options.json`
  - Thread them through to `MoonshineAsrHandler` or the Moonshine ONNX API via `--moonshine-option`
