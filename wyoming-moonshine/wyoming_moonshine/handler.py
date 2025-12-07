"""Wyoming protocol ASR handler that wraps Moonshine ONNX.

This exposes Moonshine as a Wyoming speech-to-text service so that
Home Assistant (or any other Wyoming client) can use it as an STT backend.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import wave
from pathlib import Path
from typing import Any, Dict, Optional

import moonshine_onnx
from wyoming.asr import Transcript
from wyoming.audio import AudioChunk, AudioStart
from wyoming.event import Event
from wyoming.server import AsyncEventHandler

_LOGGER = logging.getLogger(__name__)


class MoonshineAsrHandler(AsyncEventHandler):
    """Handles Wyoming ASR events and runs Moonshine for transcription.

    A single handler instance is created per TCP connection.
    We buffer audio between ``audio-start`` and ``audio-stop`` events and
    send a single ``transcript`` event back with the recognized text.
    """

    def __init__(
        self,
        reader,
        writer,
        model_name: str,
        language: Optional[str] = None,
        *,
        max_seconds: Optional[float] = None,
        moonshine_options: Optional[Dict[str, Any]] = None,
    ) -> None:
        # AsyncEventHandler in wyoming 1.8 expects reader/writer.
        super().__init__(reader, writer)
        self.model_name = model_name
        self.language = language or "en"
        self.max_seconds = max_seconds
        self._moonshine_options: Dict[str, Any] = moonshine_options or {}

        self._audio_bytes = bytearray()
        self._audio_format: Optional[AudioStart] = None
        self._too_long = False

    async def handle_event(self, event: Event) -> bool:
        """Main event loop for a single Wyoming connection.

        We respond to:
        - ``describe`` with an ``info`` event describing the ASR service
        - ``transcribe`` + audio-* events with a ``transcript`` event
        All other events are ignored but keep the connection alive.
        """

        # Service discovery -------------------------------------------------
        if event.type == "describe":
            info_event = self._build_info_event()
            _LOGGER.debug("Sending info: %s", info_event.data)
            await self.write_event(info_event)
            return True

        # Start of a new transcription request (no audio yet)
        if event.type == "transcribe":
            # We currently ignore requested name/language and always use the
            # configured model. This can be extended later.
            self._audio_bytes.clear()
            self._audio_format = None
            self._too_long = False
            _LOGGER.debug("Received transcribe request: %s", event.data)
            return True

        # Audio stream lifecycle --------------------------------------------
        if event.type == "audio-start":
            audio_start = AudioStart.from_event(event)

            if (audio_start.rate, audio_start.width, audio_start.channels) != (
                16000,
                2,
                1,
            ):
                _LOGGER.warning(
                    "Unexpected audio format: rate=%s width=%s channels=%s "
                    "(expected 16000/2/1)",
                    audio_start.rate,
                    audio_start.width,
                    audio_start.channels,
                )

            self._audio_format = audio_start
            self._audio_bytes.clear()
            self._too_long = False
            _LOGGER.debug("audio-start: resetting buffer")
            return True

        if event.type == "audio-chunk":
            if self._audio_format is None:
                _LOGGER.debug("audio-chunk before audio-start; ignoring")
                return True

            if self._too_long:
                # Already over max_seconds; ignore additional audio.
                return True

            chunk = AudioChunk.from_event(event)
            self._audio_bytes.extend(chunk.audio)

            if self.max_seconds is not None and self._audio_format is not None:
                rate = self._audio_format.rate or 16000
                width = self._audio_format.width or 2
                channels = self._audio_format.channels or 1
                bytes_per_second = rate * width * channels
                if bytes_per_second > 0:
                    duration = len(self._audio_bytes) / bytes_per_second
                    if duration > self.max_seconds:
                        _LOGGER.warning(
                            "Audio longer than max_seconds=%s (approx %.2fs); "
                            "will return empty transcript.",
                            self.max_seconds,
                            duration,
                        )
                        self._too_long = True

            return True

        if event.type == "audio-stop":
            if not self._audio_bytes or self._too_long:
                if self._too_long:
                    _LOGGER.debug(
                        "audio-stop with over-long audio; sending empty transcript"
                    )
                else:
                    _LOGGER.debug(
                        "audio-stop with empty buffer; sending empty transcript"
                    )

                await self.write_event(
                    Transcript(text="", language=self.language).event()
                )
                self._audio_bytes.clear()
                self._too_long = False
                return True

            text = await self._run_transcription()
            _LOGGER.info("Transcript: %s", text)

            transcript_event = Transcript(text=text, language=self.language).event()
            await self.write_event(transcript_event)

            # Clear for next utterance on same connection
            self._audio_bytes.clear()
            self._too_long = False
            return True

        _LOGGER.debug("Ignoring unsupported event type: %s", event.type)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_info_event(self) -> Event:
        """Build an ``info`` event describing our ASR service and model.

        Home Assistant uses this response when discovering Wyoming services
        and when you select a speech-to-text engine in an Assist pipeline.
        """

        asr_program = {
            "name": "moonshine-onnx",
            "attribution": {
                "name": "Moonshine AI",
                "url": "https://github.com/moonshine-ai/moonshine",
            },
            "installed": True,
            "description": "Moonshine ONNX speech recognition",
            "models": [
                {
                    "name": self.model_name,
                    "attribution": {
                        "name": "Moonshine AI",
                        "url": "https://github.com/moonshine-ai/moonshine",
                    },
                    "installed": True,
                    "description": self.model_name,
                    "languages": [self.language],
                    "version": self.model_name,
                }
            ],
        }

        return Event(type="info", data={"asr": [asr_program]})

    async def _run_transcription(self) -> str:
        """Run Moonshine transcription in a worker thread.

        Moonshine's ONNX ``transcribe`` call is blocking, so we offload it
        with ``asyncio.to_thread`` to avoid blocking the asyncio event loop.
        """

        assert self._audio_format is not None

        rate = self._audio_format.rate or 16000
        width = self._audio_format.width or 2
        channels = self._audio_format.channels or 1

        return await asyncio.to_thread(
            self._transcribe_sync,
            bytes(self._audio_bytes),
            rate,
            width,
            channels,
        )

    def _transcribe_sync(
        self, pcm_bytes: bytes, rate: int, width: int, channels: int
    ) -> str:
        """Synchronous part that writes a WAV file and calls Moonshine.

        Moonshine's ONNX API expects a path to an audio file:

            >>> import moonshine_onnx as moonshine
            >>> moonshine.transcribe(
            ...     moonshine.ASSETS_DIR / "beckett.wav", "moonshine/tiny"
            ... )

        so we wrap the raw PCM from Wyoming into a temporary WAV file.
        """

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

            with wave.open(tmp, "wb") as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(width)
                wav_file.setframerate(rate)
                wav_file.writeframes(pcm_bytes)

        try:
            result = moonshine_onnx.transcribe(tmp_path, self.model_name)
        finally:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass

        if isinstance(result, list):
            if not result:
                return ""

            return str(result[0])

        return str(result)
