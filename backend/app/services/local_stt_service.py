import asyncio
import os
import tempfile
import wave
from collections.abc import Awaitable, Callable


LOCAL_STT_MODEL = os.getenv("LOCAL_STT_MODEL", "small")
LOCAL_STT_DEVICE = os.getenv("LOCAL_STT_DEVICE", "cpu")
LOCAL_STT_COMPUTE_TYPE = os.getenv("LOCAL_STT_COMPUTE_TYPE", "int8")
LOCAL_STT_LANGUAGE = os.getenv("LOCAL_STT_LANGUAGE", "zh")
LOCAL_STT_SAMPLE_RATE = int(os.getenv("LOCAL_STT_SAMPLE_RATE", "16000"))
LOCAL_STT_CHUNK_SECONDS = float(os.getenv("LOCAL_STT_CHUNK_SECONDS", "4"))


class LocalSttNotConfigured(RuntimeError):
    pass


class LocalChunkStt:
    _model = None
    _model_lock = asyncio.Lock()

    def __init__(
        self,
        on_partial: Callable[[str], Awaitable[None]],
        on_final: Callable[[str], Awaitable[None]],
        on_error: Callable[[str], Awaitable[None]],
    ) -> None:
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_error = on_error
        self.audio_buffer = bytearray()
        self.started = False
        self.processing = False
        self.last_text = ""
        self.chunk_bytes = int(LOCAL_STT_SAMPLE_RATE * LOCAL_STT_CHUNK_SECONDS * 2)

    async def connect(self) -> None:
        await self._get_model()
        self.started = True

    async def send_audio(self, chunk: bytes) -> None:
        if not self.started or not chunk:
            return
        self.audio_buffer.extend(chunk)
        if len(self.audio_buffer) >= self.chunk_bytes and not self.processing:
            audio = bytes(self.audio_buffer)
            self.audio_buffer.clear()
            self.processing = True
            asyncio.create_task(self._transcribe_chunk(audio))

    async def close(self) -> None:
        self.started = False
        if self.audio_buffer:
            audio = bytes(self.audio_buffer)
            self.audio_buffer.clear()
            await self._transcribe_chunk(audio)

    @classmethod
    async def _get_model(cls):
        async with cls._model_lock:
            if cls._model is not None:
                return cls._model

            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise LocalSttNotConfigured(
                    "本地语音识别未安装：请先执行 pip install faster-whisper，并准备本地模型。"
                ) from exc

            def load_model():
                return WhisperModel(
                    LOCAL_STT_MODEL,
                    device=LOCAL_STT_DEVICE,
                    compute_type=LOCAL_STT_COMPUTE_TYPE,
                )

            try:
                cls._model = await asyncio.to_thread(load_model)
            except Exception as exc:
                raise LocalSttNotConfigured(f"本地语音识别模型加载失败：{exc}") from exc

            return cls._model

    async def _transcribe_chunk(self, audio: bytes) -> None:
        try:
            if len(audio) < LOCAL_STT_SAMPLE_RATE:
                return
            text = await asyncio.to_thread(self._transcribe_pcm16, audio)
            cleaned = text.strip()
            if cleaned and cleaned != self.last_text:
                self.last_text = cleaned
                await self.on_final(cleaned)
        except Exception as exc:
            await self.on_error(f"本地语音识别异常：{exc}")
        finally:
            self.processing = False

    @classmethod
    def _transcribe_pcm16(cls, audio: bytes) -> str:
        model = cls._model
        if model is None:
            raise RuntimeError("本地语音识别模型未加载")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            with wave.open(temp_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(LOCAL_STT_SAMPLE_RATE)
                wav_file.writeframes(audio)

            segments, _ = model.transcribe(
                temp_path,
                language=LOCAL_STT_LANGUAGE,
                vad_filter=True,
                beam_size=1,
            )
            return "".join(segment.text for segment in segments)
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
