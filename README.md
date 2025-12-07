# Home Assistant Moonshine add-ons

This repository contains Home Assistant add-ons for running Moonshine ONNX speech recognition and exposing it via the Wyoming protocol. Currently it defines a single add-on:

- `wyoming-moonshine/` – Home Assistant add-on for the Wyoming Moonshine ASR server

The add-on image is built and published to GitHub Container Registry (GHCR), and Home Assistant OS can install and run it as a custom add-on.

## Repository layout

- `wyoming-moonshine/`
  - `config.yaml` – Home Assistant add-on manifest
  - `Dockerfile` – container image build for the add-on
  - `run.sh` – container entrypoint that starts the Wyoming Moonshine server
  - `wyoming_moonshine/` – Python package implementing the Wyoming TCP server and ASR handler
- `.github/workflows/docker-publish.yml` – GitHub Actions workflow to build and publish add-on images
- `Makefile` – local tooling and local image build helpers

## Container images

The add-on image is published to GHCR under this pattern (see `wyoming-moonshine/config.yaml`):

- `ghcr.io/cronus42/wyoming-moonshine-addon-{arch}`

Architectures currently built:

- `amd64` → `ghcr.io/cronus42/wyoming-moonshine-addon-amd64`
- `aarch64` → `ghcr.io/cronus42/wyoming-moonshine-addon-aarch64`

Tags:

- `latest` – built from the `master` branch
- `<ref>` – built from tags such as `v0.1.0`

The GitHub Actions workflow (`.github/workflows/docker-publish.yml`) runs on:

- Pushes to `master`
- Pushes of tags matching `v*`

## Using this add-on with Home Assistant OS

### 1. Add this repository to the Home Assistant add-on store

In Home Assistant OS:

1. Go to **Settings → Add-ons → Add-on Store**.
2. Click the **⋮** menu in the top-right corner and choose **Repositories**.
3. Add this repository URL:

   ```text
   https://github.com/cronus42/homeassistant-moonshine-addons
   ```

4. Click **Add**, then **Close**. The store will refresh and list add-ons from this repository.

### 2. Install the Wyoming Moonshine ASR add-on

1. In the **Add-on Store**, search for **"Wyoming Moonshine ASR"**.
2. Open the add-on page and click **Install**.
3. After installation, go to the **Configuration** tab.
4. Configure options (default values are defined in `config.yaml`):

   - `model` – Moonshine model name, for example `moonshine/tiny`.
   - `language` – language code, for example `en`.
   - `log_level` – one of `DEBUG`, `INFO`, `WARNING`, `ERROR`.

5. Click **Save**.
6. On the **Info** tab, enable any of the following as needed:

   - **Start on boot**
   - **Watchdog**
   - **Auto update**

7. Click **Start** to run the add-on.

The add-on will listen on TCP port `10300` inside the Home Assistant OS host and serve the Wyoming protocol interface for speech recognition.

### 3. Use in a Home Assistant voice pipeline

To use Moonshine as the speech-to-text backend:

1. Go to **Settings → Voice assistants**.
2. Edit an existing pipeline or create a new one.
3. In the **Speech-to-text** section, select the Wyoming-based speech-to-text provider corresponding to this add-on (for example, a Wyoming Moonshine entry if configured through the UI).
4. Save the pipeline.

Any pipeline using that speech-to-text provider will send audio to the Wyoming Moonshine server running in this add-on and receive transcribed text.

## Local development

### Tooling

This repo uses a local Python virtual environment for tooling (linting, type checks, pre-commit hooks), not for the runtime Moonshine dependencies inside the container.

Create the tooling virtualenv and install dev dependencies:

```bash
make venv
```

Run lint and formatting:

```bash
make lint
make format
```

Run mypy type checks:

```bash
make typecheck
```

Install pre-commit hooks:

```bash
make pre-commit-install
```

### Build the add-on image locally

To build the `wyoming-moonshine` add-on image locally for `amd64`:

```bash
make addon-build
```

This will build a local image tagged `wyoming-moonshine-addon:local` using the Home Assistant base image (`ghcr.io/home-assistant/amd64-base:latest`).

## Notes

- The Home Assistant add-on manifest is defined in `wyoming-moonshine/config.yaml`.
- Image naming in the manifest must stay in sync with the tags produced by `.github/workflows/docker-publish.yml`.
- If you add additional architectures or new add-ons under this repository, update both the manifest(s) and the workflow(s) accordingly.