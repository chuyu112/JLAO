import asyncio
import os
import tempfile
import wave
from collections.abc import Awaitable, Callable

import numpy as np

# 繁体转简体
try:
    import opencc
    _t2s_converter = opencc.OpenCC("t2s")
except Exception:
    _t2s_converter = None


LOCAL_STT_MODEL = os.getenv("LOCAL_STT_MODEL", "small")
LOCAL_STT_DEVICE = os.getenv("LOCAL_STT_DEVICE", "cpu")
LOCAL_STT_COMPUTE_TYPE = os.getenv("LOCAL_STT_COMPUTE_TYPE", "int8")
LOCAL_STT_LANGUAGE = os.getenv("LOCAL_STT_LANGUAGE", "zh")
LOCAL_STT_SAMPLE_RATE = int(os.getenv("LOCAL_STT_SAMPLE_RATE", "16000"))
LOCAL_STT_CHUNK_SECONDS = float(os.getenv("LOCAL_STT_CHUNK_SECONDS", "4"))

# STT 引擎选择: "faster-whisper" | "funasr"
LOCAL_STT_ENGINE = os.getenv("LOCAL_STT_ENGINE", "funasr")

# FunASR 流式模型配置
FUNASR_STREAMING_MODEL = os.getenv("FUNASR_STREAMING_MODEL", "paraformer-zh-streaming")
FUNASR_VAD_MODEL = os.getenv("FUNASR_VAD_MODEL", "")  # 流式模式下不用 VAD，避免 start_idx 错误
FUNASR_PUNC_MODEL = os.getenv("FUNASR_PUNC_MODEL", "ct-punc")

# FunASR 分句参数
LOCAL_STT_FINAL_DELAY_SECONDS = float(os.getenv("LOCAL_STT_FINAL_DELAY_SECONDS", "1.5"))
LOCAL_STT_MAX_SEGMENT_SECONDS = float(os.getenv("LOCAL_STT_MAX_SEGMENT_SECONDS", "6"))
LOCAL_STT_SENTENCE_END_PUNCTUATION = os.getenv("LOCAL_STT_SENTENCE_END_PUNCTUATION", "。！？")


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

        # FunASR streaming state
        self._funasr_cache: dict = {}
        self._funasr_chunk_samples = 9600  # 600ms @ 16kHz
        self._silence_timer: asyncio.Task | None = None
        self._max_segment_timer: asyncio.Task | None = None
        self._final_delay_seconds = LOCAL_STT_FINAL_DELAY_SECONDS
        self._max_segment_seconds = LOCAL_STT_MAX_SEGMENT_SECONDS
        self._sentence_end_punctuation = LOCAL_STT_SENTENCE_END_PUNCTUATION

    async def connect(self) -> None:
        await self._get_model()
        self.started = True
        if LOCAL_STT_ENGINE == "funasr":
            self._funasr_cache = {}
            self.last_text = ""

    async def send_audio(self, chunk: bytes) -> None:
        if not self.started or not chunk:
            return
        self.audio_buffer.extend(chunk)

        if LOCAL_STT_ENGINE == "funasr":
            await self._send_audio_funasr()
        else:
            await self._send_audio_whisper()

    async def _send_audio_funasr(self) -> None:
        bytes_per_chunk = self._funasr_chunk_samples * 2  # 16bit = 2 bytes
        while len(self.audio_buffer) >= bytes_per_chunk and not self.processing:
            audio = bytes(self.audio_buffer[:bytes_per_chunk])
            self.audio_buffer = self.audio_buffer[bytes_per_chunk:]
            self.processing = True
            asyncio.create_task(self._transcribe_funasr_chunk(audio, is_final=False))

    async def _send_audio_whisper(self) -> None:
        if len(self.audio_buffer) >= self.chunk_bytes and not self.processing:
            audio = bytes(self.audio_buffer)
            self.audio_buffer.clear()
            self.processing = True
            asyncio.create_task(self._transcribe_whisper_chunk(audio))

    async def close(self) -> None:
        self.started = False
        if LOCAL_STT_ENGINE == "funasr":
            self._cancel_silence_timer()
            self._cancel_max_segment_timer()
        if self.audio_buffer:
            audio = bytes(self.audio_buffer)
            self.audio_buffer.clear()
            if LOCAL_STT_ENGINE == "funasr":
                await self._transcribe_funasr_chunk(audio, is_final=True)
            else:
                await self._transcribe_whisper_chunk(audio)

    # ---- Timer helpers ----

    def _reset_silence_timer(self) -> None:
        """收到新音频/识别结果时重置静音定时器"""
        self._cancel_silence_timer()
        self._silence_timer = asyncio.create_task(self._silence_timer_task())

    def _cancel_silence_timer(self) -> None:
        if self._silence_timer and not self._silence_timer.done():
            self._silence_timer.cancel()
        self._silence_timer = None

    def _start_max_segment_timer(self) -> None:
        """开始最大段长计时"""
        self._cancel_max_segment_timer()
        if self._max_segment_seconds > 0:
            self._max_segment_timer = asyncio.create_task(self._max_segment_timer_task())

    def _cancel_max_segment_timer(self) -> None:
        if self._max_segment_timer and not self._max_segment_timer.done():
            self._max_segment_timer.cancel()
        self._max_segment_timer = None

    async def _silence_timer_task(self) -> None:
        """静音超时 → 输出当前累积文本"""
        try:
            await asyncio.sleep(self._final_delay_seconds)
            if self.started and self.last_text:
                text = self.last_text
                self.last_text = ""
                self._funasr_cache = {}
                self._cancel_max_segment_timer()
                await self.on_final(text)
        except asyncio.CancelledError:
            pass

    async def _max_segment_timer_task(self) -> None:
        """最大段长超时 → 强制输出当前累积文本"""
        try:
            await asyncio.sleep(self._max_segment_seconds)
            if self.started and self.last_text:
                text = self.last_text
                self.last_text = ""
                self._funasr_cache = {}
                self._cancel_silence_timer()
                # 输出后重新开始计时，因为可能还在说话
                self._start_max_segment_timer()
                await self.on_final(text)
        except asyncio.CancelledError:
            pass

    async def _finalize_text(self) -> None:
        """立即输出当前累积文本并重置"""
        if not self.last_text:
            return
        text = self.last_text
        self.last_text = ""
        self._funasr_cache = {}
        self._cancel_silence_timer()
        self._cancel_max_segment_timer()
        await self.on_final(text)

    # ---- Model loading ----

    @classmethod
    async def _get_model(cls):
        async with cls._model_lock:
            if cls._model is not None:
                return cls._model

            if LOCAL_STT_ENGINE == "funasr":
                cls._model = await cls._load_funasr_model()
            else:
                cls._model = await cls._load_faster_whisper_model()

            return cls._model

    @classmethod
    async def _load_funasr_model(cls):
        try:
            from funasr import AutoModel
        except ImportError as exc:
            raise LocalSttNotConfigured(
                "本地语音识别未安装：请先执行 pip install funasr"
            ) from exc

        def load_model():
            kwargs = {
                "model": FUNASR_STREAMING_MODEL,
                "device": LOCAL_STT_DEVICE,
            }
            if FUNASR_VAD_MODEL:
                kwargs["vad_model"] = FUNASR_VAD_MODEL
            if FUNASR_PUNC_MODEL:
                kwargs["punc_model"] = FUNASR_PUNC_MODEL
            return AutoModel(**kwargs)

        try:
            return await asyncio.to_thread(load_model)
        except Exception as exc:
            raise LocalSttNotConfigured(f"FunASR 流式模型加载失败：{exc}") from exc

    @classmethod
    async def _load_faster_whisper_model(cls):
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
            return await asyncio.to_thread(load_model)
        except Exception as exc:
            raise LocalSttNotConfigured(f"本地语音识别模型加载失败：{exc}") from exc

    # ---- Transcription ----

    async def _transcribe_funasr_chunk(self, audio: bytes, is_final: bool = False) -> None:
        try:
            pcm = np.frombuffer(audio, dtype=np.int16)
            if len(pcm) == 0:
                return

            text, self._funasr_cache = await asyncio.to_thread(
                self._generate_funasr, pcm, is_final, self._funasr_cache
            )
            cleaned = text.strip()

            if not cleaned:
                return

            # 繁体转简体
            if _t2s_converter:
                cleaned = _t2s_converter.convert(cleaned)

            self.last_text = cleaned
            await self.on_partial(cleaned)

            # 重置静音定时器（有新识别结果，说明还在说话）
            self._reset_silence_timer()

            # 启动最大段长计时器（仅在还没有的时候启动）
            if not self._max_segment_timer or self._max_segment_timer.done():
                self._start_max_segment_timer()

            # 句末标点触发 final（仅 。！？，说明一句话结束了）
            if cleaned and cleaned[-1] in self._sentence_end_punctuation:
                await self._finalize_text()

            # 显式 final（关闭时）
            if is_final:
                await self._finalize_text()

        except Exception as exc:
            await self.on_error(f"FunASR 识别异常：{exc}")
        finally:
            self.processing = False

    @classmethod
    def _generate_funasr(cls, pcm: np.ndarray, is_final: bool, cache: dict) -> tuple[str, dict]:
        model = cls._model
        if model is None:
            raise RuntimeError("FunASR 模型未加载")

        result = model.generate(
            input=pcm,
            cache=cache,
            is_final=is_final,
        )

        text = ""
        if result and len(result) > 0:
            text = result[0].get("text", "")
        return text, cache

    async def _transcribe_whisper_chunk(self, audio: bytes) -> None:
        try:
            if len(audio) < LOCAL_STT_SAMPLE_RATE:
                return
            text = await asyncio.to_thread(self._transcribe_pcm16_whisper, audio)
            cleaned = text.strip()
            if cleaned and cleaned != self.last_text:
                self.last_text = cleaned
                await self.on_final(cleaned)
        except Exception as exc:
            await self.on_error(f"本地语音识别异常：{exc}")
        finally:
            self.processing = False

    @classmethod
    def _transcribe_pcm16_whisper(cls, audio: bytes) -> str:
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
