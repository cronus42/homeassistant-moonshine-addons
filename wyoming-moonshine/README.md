# Wyoming Moonshine ASR (Home Assistant add-on)

This add-on runs the Moonshine ONNX speech recognition server and exposes it
via the Wyoming protocol for Home Assistant voice pipelines.

Configuration options:

- `model`: Moonshine model name (e.g. `moonshine/tiny`, `moonshine/base`).
- `language`: Language code to report to Home Assistant (e.g. `en`, `en-US`).
- `log_level`: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`).

Once installed and started, add a **Wyoming** integration in Home Assistant
pointing at this add-on's host and port (default `10300`), then select it as
the Speech-to-text provider in your Assist pipeline.
