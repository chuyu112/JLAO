from datetime import datetime
from uuid import uuid4

from app.schemas import ReplayReport, Suggestion, TranscriptSegment


def build_replay_report(session_id: str, transcripts: list[TranscriptSegment], suggestions: list[Suggestion]) -> ReplayReport:
    used = [item.content for item in suggestions if item.status.value in ["已使用", "已接受", "已复制"]]
    virtual_replies = [item.content for item in suggestions if "模拟回复" in item.type or item.type == "虚拟场控回复"]
    risks = [item.content for item in suggestions if item.type in ["风险提醒", "风险改写"]]
    missed = [item.content for item in suggestions if item.type in ["漏讲提醒", "主播补充话术"]]
    questions = [item.text for item in transcripts if any(word in item.text for word in ["吗", "有没有", "会不会", "多少"])]

    summary = (
        f"公开视频号翡翠直播观察报告：共记录 {len(transcripts)} 条转写，生成 {len(suggestions)} 条虚拟场控建议。"
        "当前 MVP 只做平台外观察、训练样本沉淀和虚拟回复沙盘，不向视频号发送任何内容。"
    )

    return ReplayReport(
        id=f"rep-{uuid4().hex[:12]}",
        session_id=session_id,
        summary=summary,
        useful_scripts=(used + virtual_replies)[:8],
        missed_points=missed[:8],
        risk_warnings=risks[:8],
        audience_questions=questions[:8],
        next_suggestions=[
            "把本场可学习话术加入新人训练样本库，标注适用场景。",
            "把高风险表达和安全改写整理成训练样本，开播前让新人主播朗读演练。",
            "从用户问题线索中整理价格、证书、瑕疵、自然光四类标准回答。",
        ],
        created_at=datetime.utcnow(),
    )

