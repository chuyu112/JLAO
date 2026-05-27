from datetime import datetime, timezone
from uuid import uuid4

from app.schemas import AgentUtterance, Product, VirtualCustomerEvent, WikiChunk
from app.services.compliance_service import find_risk_terms


VIRTUAL_SANDBOX_TARGET = "虚拟场控沙盘（仅模拟，不发送）"
VIRTUAL_REVIEW_TARGET = "虚拟场控沙盘（仅模拟，不发送，需人工审核）"


AGENT_DEFINITIONS = [
    ("agent-atmosphere", "气氛小助手", "气氛组"),
    ("agent-product", "翡翠商品专家", "商品专家"),
    ("agent-customer", "客户关系官", "客户关系"),
    ("agent-risk", "风控审核员", "风控"),
    ("agent-conversion", "成交转化助手", "成交转化"),
]


def classify_send_mode(content: str, agent_role: str = "") -> tuple[str, str]:
    terms = find_risk_terms(content)
    if terms or agent_role == "风控" and any(word in content for word in ["保证升值", "稳赚不赔", "绝对"]):
        return "高", "blocked"
    if agent_role in ["成交转化", "客户关系"] and any(word in content for word in ["价格", "下手", "预算", "老客"]):
        return "中", "needs_review"
    return "低", "auto_simulated"


def generate_agent_utterances(
    session_id: str,
    product: Product | None,
    transcript_text: str,
    wiki_hits: list[WikiChunk],
    customer_events: list[VirtualCustomerEvent],
) -> list[AgentUtterance]:
    now = datetime.now(timezone.utc)
    wiki_ids = [chunk.id for chunk in wiki_hits]
    event_ids = [event.id for event in customer_events]
    product_name = product.name if product else "当前商品"
    product_point = product.selling_points[0] if product and product.selling_points else "自然光、证书和细节"
    wiki_hint = wiki_hits[0].heading if wiki_hits else "当前直播上下文"
    high_value_event = next((event for event in customer_events if event.event_type == "高价值进房"), None)

    templates = {
        "气氛组": f"新进来的朋友可以先看 {product_name} 的上手效果，想看自然光可以扣 1。",
        "商品专家": f"{product_name} 建议补充讲清楚：{product_point}，再说明实物以自然光为准。",
        "客户关系": (
            f"{high_value_event.customer_nickname} 是高价值客户，先欢迎，再按偏好引导看 {product_name}。"
            if high_value_event
            else "有老客进房时先轻声欢迎，不要直接暴露客户隐私和购买记录。"
        ),
        "风控": _risk_content(transcript_text, wiki_hint),
        "成交转化": f"如果用户问价格，先把 {product_name} 的品质依据讲清楚，再引导合适再下手。",
    }

    utterances: list[AgentUtterance] = []
    for agent_id, name, role in AGENT_DEFINITIONS:
        content = templates[role]
        risk_level, send_mode = classify_send_mode(content, role)
        utterances.append(
            AgentUtterance(
                id=f"utt-{uuid4().hex[:12]}",
                session_id=session_id,
                agent_id=agent_id,
                agent_name=name,
                agent_role=role,
                target=VIRTUAL_SANDBOX_TARGET if send_mode == "auto_simulated" else VIRTUAL_REVIEW_TARGET,
                content=content,
                risk_level=risk_level,
                send_mode=send_mode,
                status="仅模拟",
                trigger_reason=f"基于公开视频号直播观察、商品、Wiki：{wiki_hint}",
                wiki_chunk_ids=wiki_ids,
                customer_event_ids=event_ids,
                created_at=now,
            )
        )
    return utterances


def _risk_content(transcript_text: str, wiki_hint: str) -> str:
    terms = find_risk_terms(transcript_text)
    if terms:
        return f"检测到高风险表达：{'、'.join(terms)}。根据 {wiki_hint}，这类话术必须拦截，不能自动发送。"
    return f"当前未发现硬性风险词。继续参考 {wiki_hint}，价格、售后、保真和升值相关内容要人工确认。"
