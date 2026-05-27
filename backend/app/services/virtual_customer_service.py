from datetime import datetime, timezone
from uuid import uuid4

from app.schemas import Product, VirtualCustomer, VirtualCustomerEvent


def generate_customer_events(
    session_id: str,
    customers: list[VirtualCustomer],
    product: Product | None,
    transcript_text: str,
    existing_event_count: int = 0,
) -> list[VirtualCustomerEvent]:
    events: list[VirtualCustomerEvent] = []
    text = transcript_text or ""

    for customer in customers:
        match_reasons = _match_reasons(customer, product, text)
        if not match_reasons and existing_event_count > 0:
            continue

        if customer.level in ["高价值", "VIP", "老客"] and match_reasons:
            events.append(
                _new_event(
                    session_id,
                    customer,
                    "高价值进房",
                    f"{customer.nickname} 进房，偏好与当前内容匹配：{'、'.join(match_reasons)}。",
                    customer.relationship_strategy or "先欢迎老客，再提醒主播展示客户关心的细节。",
                    priority=3,
                )
            )
        elif match_reasons and customer.activity_level >= 0.5:
            events.append(
                _new_event(
                    session_id,
                    customer,
                    "兴趣表达",
                    f"{customer.nickname} 对当前内容产生兴趣：{'、'.join(match_reasons)}。",
                    "客户偏好命中当前商品或主播话术。",
                    priority=2,
                )
            )

        if customer.common_questions and any(word in text for word in ["自然光", "证书", "价格", "有裂", "售后"]):
            question = customer.common_questions[0]
            events.append(
                _new_event(
                    session_id,
                    customer,
                    "客户提问",
                    f"{customer.nickname}：{question}",
                    "主播讲到客户常问锚点，触发虚拟客户提问。",
                    priority=2,
                )
            )

        if events:
            break

    if not events and customers and existing_event_count == 0:
        customer = customers[0]
        events.append(
            _new_event(
                session_id,
                customer,
                "客户进房",
                f"{customer.nickname} 进入直播间。",
                "启动虚拟客户池，演示客户记忆和互动。",
                priority=1,
            )
        )

    return events[:3]


def _match_reasons(customer: VirtualCustomer, product: Product | None, text: str) -> list[str]:
    reasons: list[str] = []
    if product:
        if product.color and any(color in product.color or color in text for color in customer.preferred_colors):
            reasons.append(f"偏好颜色 {product.color}")
        if product.category and product.category in customer.preferred_categories:
            reasons.append(f"偏好品类 {product.category}")
    for question in customer.common_questions:
        anchor = question.replace("？", "").replace("?", "")
        if anchor and any(part and part in text for part in [anchor, "自然光", "证书", "价格"]):
            reasons.append("常问问题被触发")
            break
    return reasons


def _new_event(
    session_id: str,
    customer: VirtualCustomer,
    event_type: str,
    content: str,
    trigger_reason: str,
    priority: int,
) -> VirtualCustomerEvent:
    return VirtualCustomerEvent(
        id=f"vce-{uuid4().hex[:12]}",
        session_id=session_id,
        customer_id=customer.id,
        customer_nickname=customer.nickname,
        customer_level=customer.level,
        event_type=event_type,
        content=content,
        trigger_reason=trigger_reason,
        priority=priority,
        created_at=datetime.now(timezone.utc),
    )
