"""Entry point for the Moonshine Wyoming ASR server.

Run with:

    python -m wyoming_moonshine --uri tcp://0.0.0.0:10300 \
        --model moonshine/tiny --language en

This starts a Wyoming server that Home Assistant can use as a local
speech-to-text engine via the Wyoming integration.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Any, Dict, Iterable
from urllib.parse import urlparse

from wyoming.server import AsyncTcpServer, AsyncUnixServer

from .handler import MoonshineAsrHandler

# Built-in profiles that tune model/language and simple limits.
PROFILES = {
    "fast-en": {
        "model": "moonshine/tiny",
        "language": "en",
        "max_seconds": 15.0,
    },
    "accurate-en": {
        "model": "moonshine/base",
        "language": "en",
        "max_seconds": 30.0,
    },
}


def _parse_moonshine_options(pairs: Iterable[str]) -> Dict[str, Any]:
    """Parse KEY=VALUE pairs for --moonshine-option.

    Values are coerced to bool/int/float when possible, otherwise left as strings.
    """

    options: Dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid --moonshine-option {pair!r}, expected KEY=VALUE")
        key, value = pair.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError("Moonshine option key cannot be empty")

        lower = value.lower()
        if lower in {"true", "false"}:
            coerced: Any = lower == "true"
        else:
            try:
                coerced = int(value)
            except ValueError:
                try:
                    coerced = float(value)
                except ValueError:
                    coerced = value

        options[key] = coerced

    return options


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wyoming protocol server for Moonshine ONNX speech recognition.",
    )

    parser.add_argument(
        "--uri",
        default="tcp://0.0.0.0:10300",
        help="Wyoming server URI, e.g. tcp://0.0.0.0:10300",
    )
    parser.add_argument(
        "--model",
        default="moonshine/tiny",
        help=(
            "Moonshine model name, e.g. moonshine/tiny, moonshine/base, "
            "moonshine/tiny-ko, ..."
        ),
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Language code reported to clients (e.g. en, en-US, ko)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help=(
            "Named profile that sets model/language and simple limits, e.g. "
            "fast-en or accurate-en. Explicit --model/--language override the profile."
        ),
    )
    parser.add_argument(
        "--moonshine-option",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Extra KEY=VALUE options forwarded to moonshine_onnx.transcribe. "
            "Can be passed multiple times."
        ),
    )

    return parser.parse_args()


async def _async_main() -> None:
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger = logging.getLogger(__name__)

    # Resolve profile-based defaults.
    model_name = args.model
    language = args.language
    max_seconds = None

    if args.profile:
        profile = PROFILES.get(args.profile)
        if profile is None:
            known_profiles = ", ".join(sorted(PROFILES))
            raise ValueError(
                f"Unknown profile {args.profile!r}. "
                f"Known profiles: {known_profiles}"
            )

        # Explicit CLI flags win over profile defaults.
        if "--model" not in sys.argv:
            model_name = profile.get("model", model_name)
        if "--language" not in sys.argv:
            language = profile.get("language", language)
        max_seconds = profile.get("max_seconds")

    moonshine_options = _parse_moonshine_options(args.moonshine_option)

    # Factory to create a new handler per connection.
    # Wyoming 1.8 calls this as handler_factory(reader, writer).
    def handler_factory(reader, writer) -> MoonshineAsrHandler:
        return MoonshineAsrHandler(
            reader,
            writer,
            model_name,
            language,
            max_seconds=max_seconds,
            moonshine_options=moonshine_options,
        )

    parsed = urlparse(args.uri)

    if parsed.scheme == "tcp":
        host = parsed.hostname or "0.0.0.0"
        port = parsed.port or 10300
        server = AsyncTcpServer(host, port)
        bind_desc = f"tcp://{host}:{port}"
    elif parsed.scheme == "unix":
        if not parsed.path:
            raise ValueError(f"UNIX URI must have a path: {args.uri}")
        server = AsyncUnixServer(parsed.path)
        bind_desc = f"unix://{parsed.path}"
    else:
        raise ValueError(f"Unsupported URI scheme in {args.uri!r} (expected tcp:// or unix://)")

    logger.info(
        "Starting Moonshine Wyoming ASR server on %s with model %s (language=%s)",
        bind_desc,
        model_name,
        language,
    )

    await server.run(handler_factory)


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":  # pragma: no cover
    main()
