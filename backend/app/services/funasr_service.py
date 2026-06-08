"""FunASR 流式语音识别服务。

从 local_stt_service 导入流式实现，保持向后兼容。
"""

from app.services.local_stt_service import LocalChunkStt as FunasrChunkStt, LocalSttNotConfigured as FunasrNotConfigured

# 别名，保持与旧代码兼容
LocalChunkStt = FunasrChunkStt
