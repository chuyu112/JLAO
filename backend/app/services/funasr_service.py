"""FunASR 流式语音识别服务。

使用 FunASR 实现本地实时语音转文字，替代阿里云语音识别。
"""

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable


logger = logging.getLogger(__name__)

# FunASR 配置
FUNASR_MODEL = os.getenv("FUNASR_MODEL", "paraformer-zh")
FUNASR_DEVICE = os.getenv("FUNASR_DEVICE", "cpu")
FUNASR_SAMPLE_RATE = int(os.getenv("FUNASR_SAMPLE_RATE", "16000"))
FUNASR_CHUNK_SECONDS = float(os.getenv("FUNASR_CHUNK_SECONDS", "4"))


class FunasrNotConfigured(RuntimeError):
    """FunASR 未正确配置。"""

    pass


class FunasrChunkStt:
    """基于 FunASR 的流式语音识别器。"""

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
        self.chunk_bytes = int(FUNASR_SAMPLE_RATE * FUNASR_CHUNK_SECONDS * 2)

    async def connect(self) -> None:
        """连接并加载模型。"""
        await self._get_model()
        self.started = True

    async def send_audio(self, chunk: bytes) -> None:
        """发送音频数据块。"""
        if not self.started or not chunk:
            return
        self.audio_buffer.extend(chunk)
        if len(self.audio_buffer) >= self.chunk_bytes and not self.processing:
            audio = bytes(self.audio_buffer)
            self.audio_buffer.clear()
            self.processing = True
            asyncio.create_task(self._transcribe_chunk(audio))

    async def close(self) -> None:
        """关闭识别器，处理剩余音频。"""
        self.started = False
        if self.audio_buffer:
            audio = bytes(self.audio_buffer)
            self.audio_buffer.clear()
            await self._transcribe_chunk(audio)

    @classmethod
    async def _get_model(cls):
        """获取或加载 FunASR 模型。"""
        async with cls._model_lock:
            if cls._model is not None:
                return cls._model

            try:
                from funasr import AutoModel
            except ImportError as exc:
                raise FunasrNotConfigured(
                    "FunASR 未安装：请先执行 pip install funasr"
                ) from exc

            def load_model():
                # 使用 Paraformer 模型，中文识别效果最佳
                return AutoModel(
                    model=FUNASR_MODEL,
                    device=FUNASR_DEVICE,
                )

            try:
                logger.info("正在加载 FunASR 模型: %s", FUNASR_MODEL)
                cls._model = await asyncio.to_thread(load_model)
                logger.info("FunASR 模型加载完成")
            except Exception as exc:
                raise FunasrNotConfigured(f"FunASR 模型加载失败：{exc}") from exc

            return cls._model

    async def _transcribe_chunk(self, audio: bytes) -> None:
        """转录音频块。"""
        try:
            if len(audio) < FUNASR_SAMPLE_RATE:
                return
            text = await asyncio.to_thread(self._transcribe_pcm16, audio)
            cleaned = text.strip()
            if cleaned and cleaned != self.last_text:
                self.last_text = cleaned
                await self.on_final(cleaned)
        except Exception as exc:
            await self.on_error(f"FunASR 识别异常：{exc}")
        finally:
            self.processing = False

    @classmethod
    def _transcribe_pcm16(cls, audio: bytes) -> str:
        """将 PCM16 音频转录为文字。"""
        import tempfile
        import wave

        model = cls._model
        if model is None:
            raise RuntimeError("FunASR 模型未加载")

        # 创建临时 WAV 文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            with wave.open(temp_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(FUNASR_SAMPLE_RATE)
                wav_file.writeframes(audio)

            # 使用 FunASR 进行识别
            result = model.generate(
                input=temp_path,
                batch_size=1,
            )

            # 提取识别结果
            if result and len(result) > 0:
                text = result[0].get("text", "")
                return text
            return ""
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


# 别名，保持与旧代码兼容
LocalChunkStt = FunasrChunkStt
