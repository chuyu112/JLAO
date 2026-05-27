from app.schemas import Product, Suggestion, TranscriptSegment
from app.services.compliance_service import find_risk_terms, rewrite_if_risky
from app.services.context_service import build_context
from datetime import datetime, timezone
from uuid import uuid4


SIMULATION_PREFIX = "【仅模拟，不发送】"
VIRTUAL_CONTROL_ROLE = "虚拟场控"


def _new_suggestion(
    session_id: str,
    product_id: str | None,
    type_: str,
    target_role: str,
    priority: int,
    risk_level: str,
    content: str,
    reason: str,
    source_context: str,
) -> Suggestion:
    now = datetime.now(timezone.utc)
    return Suggestion(
        id=f"sug-{uuid4().hex[:12]}",
        session_id=session_id,
        product_id=product_id,
        type=type_,
        target_role=target_role,
        priority=priority,
        risk_level=risk_level,
        content=content,
        reason=reason,
        source_context=source_context,
        created_at=now,
        updated_at=now,
    )


def _virtual_reply(content: str) -> str:
    return content if content.startswith(SIMULATION_PREFIX) else f"{SIMULATION_PREFIX}{content}"


def generate_suggestions(
    session_id: str,
    product: Product | None,
    transcripts: list[TranscriptSegment],
) -> list[Suggestion]:
    if not transcripts:
        return []

    latest = transcripts[-1].text
    context = build_context(product, transcripts)
    suggestions: list[Suggestion] = []

    if find_risk_terms(latest):
        rewritten, risk_level, terms = rewrite_if_risky(latest)
        suggestions.append(
            _new_suggestion(
                session_id,
                product.id if product else None,
                "风险改写",
                VIRTUAL_CONTROL_ROLE,
                3,
                risk_level,
                _virtual_reply(f"刚才话术包含风险词：{', '.join(terms)}。建议改成：{rewritten}"),
                "公开视频号直播观察中检测到绝对化、投资承诺或功效承诺类表达。",
                context,
            )
        )

    if "便宜" in latest or "价格" in latest:
        suggestions.append(
            _new_suggestion(
                session_id,
                product.id if product else None,
                "用户问题模拟回复",
                VIRTUAL_CONTROL_ROLE,
                2,
                "低",
                _virtual_reply("可以这样回：价格我们会结合品质、证书和完美度一起说，先把细节看清楚，合适再下手。"),
                "公开视频号直播观察中出现价格问题线索，需要模拟安全、低压的场控回复。",
                context,
            )
        )

    if product:
        missing = []
        recent_text = " ".join(item.text for item in transcripts[-5:])
        if "证书" not in recent_text and product.certificate:
            missing.append("证书")
        if "圈口" not in recent_text and product.category == "手镯":
            missing.append("圈口")
        if "自然光" not in recent_text:
            missing.append("自然光效果")
        if "棉" not in recent_text and product.flaws:
            missing.append("棉、纹、裂等瑕疵说明")

        if missing:
            suggestions.append(
                _new_suggestion(
                    session_id,
                    product.id,
                    "主播补充话术",
                    VIRTUAL_CONTROL_ROLE,
                    2,
                    "低",
                    _virtual_reply(f"可以补充：{ '、'.join(missing) }。先把关键信息讲清楚，用户会更安心。"),
                    "公开视频号直播观察中发现关键交易信息还没有在最近话术里出现。",
                    context,
                )
            )

        if any(word in latest for word in ["看", "上手", "飘花", "颜色", "冰感"]):
            first_point = product.selling_points[0] if product.selling_points else "品质细节"
            suggestions.append(
                _new_suggestion(
                    session_id,
                    product.id,
                    "主播补充话术",
                    VIRTUAL_CONTROL_ROLE,
                    2,
                    "低",
                    _virtual_reply(
                        f"这件可以围绕“{first_point}”继续讲，再顺手补一句：{product.cautions or '实物效果以自然光为准'}。"
                    ),
                    "公开视频号直播观察中主播正在展示商品细节，适合补充专业但口语化的卖点。",
                    context,
                )
            )

    if any(word in latest for word in ["自然光", "上手", "证书", "有裂", "会不会"]):
        suggestions.append(
            _new_suggestion(
                session_id,
                product.id if product else None,
                "虚拟场控回复",
                VIRTUAL_CONTROL_ROLE,
                1,
                "低",
                _virtual_reply("想看自然光的扣 1，想看上手效果的扣 2，想看证书近景的扣 3。"),
                "公开视频号直播观察中出现了查看细节的需求，适合模拟一次选择型互动。",
                context,
            )
        )

    return suggestions[:3]

