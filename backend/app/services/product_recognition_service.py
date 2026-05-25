from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.schemas import Product
from app.repositories import save_live_session
from app.state import app_state
from app.ws.manager import manager

_scores: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
_last_signal: dict[str, dict[str, float | str]] = {}

DECAY = 0.7
IMAGE_WEIGHT = 1.4
TEXT_WEIGHT = 1.0
SWITCH_THRESHOLD = 0.6
GAP_THRESHOLD = 0.2

# ----- 维度词库 -----
WATER_TERMS: dict[str, list[str]] = {
    "玻璃种": ["玻璃种", "玻璃"],
    "冰种": ["冰种", "冰底", "高冰", "冰透", "冰冰"],
    "糯冰": ["糯冰", "冰糯", "细糯冰"],
    "细糯": ["细糯", "细糯种", "细腻"],
    "糯种": ["糯种", "糯底", "糯"],
    "豆种": ["豆种", "豆底", "豆子"],
}

SUBJECT_TERMS: dict[str, list[str]] = {
    "手镯": ["手镯", "镯子", "镯", "圆条", "正圈", "贵妃镯", "平安镯"],
    "观音": ["观音", "观音菩萨", "观世音"],
    "佛公": ["佛公", "弥勒佛", "佛", "笑佛"],
    "蛋面": ["蛋面", "戒面", "蛋", "鸽子蛋"],
    "葫芦": ["葫芦", "福禄"],
    "叶子": ["叶子", "树叶", "金枝玉叶"],
    "平安扣": ["平安扣", "扣子"],
    "无事牌": ["无事牌", "牌子"],
    "如意": ["如意", "如意头"],
    "貔貅": ["貔貅", "皮丘"],
    "珠串": ["珠串", "手串", "珠子", "珠链", "项链"],
    "山水": ["山水", "山水牌"],
}

EXTRA_TERMS: dict[str, list[str]] = {
    "镶嵌": ["镶嵌", "金镶", "银镶", "镶钻", "包金", "包边"],
    "裸石": ["裸石", "没镶", "未镶嵌"],
    "飘花": ["飘花", "飘蓝花", "飘绿花"],
    "满色": ["满色", "满绿", "满紫"],
    "带底色": ["带底色", "底色"],
}


def _decay_scores(session_id: str) -> None:
    bucket = _scores[session_id]
    for pid in list(bucket):
        bucket[pid] *= DECAY
        if bucket[pid] < 0.05:
            del bucket[pid]


def match_products_by_image(image_path: Path) -> dict[str, float]:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {}

    image = cv2.imread(str(image_path))
    if image is None:
        return {}

    h, w = image.shape[:2]
    if h == 0 or w == 0:
        return {}

    cx, cy = w // 2, h // 2
    half_w = max(40, int(w * 0.45))
    half_h = max(40, int(h * 0.45))
    x1 = max(0, cx - half_w)
    x2 = min(w, cx + half_w)
    y1 = max(0, cy - half_h)
    y2 = min(h, cy + half_h)
    center = image[y1:y2, x1:x2]
    if center.size == 0:
        return {}

    hsv = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)
    h_chan = hsv[..., 0]
    s_chan = hsv[..., 1]
    v_chan = hsv[..., 2]

    valid = (s_chan > 32) & (v_chan > 60) & (v_chan < 240)
    valid_count = int(valid.sum())
    if valid_count < 100:
        return {}

    valid_h = h_chan[valid]

    green = int(((valid_h >= 35) & (valid_h <= 85)).sum())
    cyan = int(((valid_h >= 86) & (valid_h <= 105)).sum())
    blue = int(((valid_h >= 106) & (valid_h <= 125)).sum())
    purple = int(((valid_h >= 126) & (valid_h <= 160)).sum())

    whitish = int(((s_chan < 40) & (v_chan > 170)).sum())
    total = max(1, h_chan.size)

    color_ratios = {
        "green": green / total,
        "cyan": cyan / total,
        "blue": blue / total,
        "purple": purple / total,
        "white": whitish / total,
    }

    scores: dict[str, float] = {}
    for product in app_state.products.values():
        score = 0.0
        c = (product.color or "") + (product.name or "")
        if "阳绿" in c or ("绿" in c and "晴水" not in c):
            score = color_ratios["green"] * 6
        elif "紫" in c:
            score = color_ratios["purple"] * 6
        elif "晴水" in c:
            score = color_ratios["cyan"] * 4 + color_ratios["green"] * 1.2 + color_ratios["white"] * 1
        elif "蓝" in c:
            score = color_ratios["blue"] * 6 + color_ratios["cyan"] * 2
        elif "冰" in c or "飘花" in c or "白" in c:
            score = color_ratios["white"] * 4 + color_ratios["cyan"] * 1.5
        if score > 0.03:
            scores[product.id] = round(score, 4)

    if scores:
        print(f"[REC_IMG] ratios={color_ratios} scores={scores}")
    return scores


def _product_keywords(product: Product) -> list[str]:
    keywords: list[str] = []
    if product.name:
        keywords.append(product.name)
    if product.category:
        keywords.append(product.category)
    if product.color:
        keywords.append(product.color)
    color = product.color or ""
    if "晴水" in color:
        keywords += ["晴水"]
    if "蓝" in color:
        keywords += ["蓝水"]
    if "紫" in color:
        keywords += ["紫罗兰", "紫色"]
    if "阳绿" in color:
        keywords += ["阳绿"]
    if "冰" in color or "飘" in color:
        keywords += ["冰种", "飘花"]
    keywords += [item for item in product.selling_points[:2] if item]
    return [k for k in keywords if k and len(k) >= 2]


def match_products_by_text(text: str) -> dict[str, float]:
    if not text:
        return {}
    scores: dict[str, float] = {}
    for product in app_state.products.values():
        score = 0.0
        if product.name and product.name in text:
            score += 4
        if product.category and product.category in text:
            score += 1
        if product.color and product.color in text:
            score += 2
        for kw in _product_keywords(product):
            if kw and kw != product.name and kw in text:
                score += 0.6
        if score > 0:
            scores[product.id] = round(score, 4)
    if scores:
        print(f"[REC_TXT] text={text[:40]!r} scores={scores}")
    return scores


def extract_color_from_image(image_path: Path) -> str:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return ""

    image = cv2.imread(str(image_path))
    if image is None:
        return ""

    h, w = image.shape[:2]
    if h == 0 or w == 0:
        return ""

    cx, cy = w // 2, h // 2
    half_w = max(40, int(w * 0.45))
    half_h = max(40, int(h * 0.45))
    x1 = max(0, cx - half_w)
    x2 = min(w, cx + half_w)
    y1 = max(0, cy - half_h)
    y2 = min(h, cy + half_h)
    center = image[y1:y2, x1:x2]
    if center.size == 0:
        return ""

    hsv = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)
    h_chan = hsv[..., 0]
    s_chan = hsv[..., 1]
    v_chan = hsv[..., 2]

    valid = (s_chan > 32) & (v_chan > 60) & (v_chan < 240)
    valid_count = int(valid.sum())
    if valid_count < 100:
        return ""

    valid_h = h_chan[valid]
    green = int(((valid_h >= 35) & (valid_h <= 85)).sum())
    cyan = int(((valid_h >= 86) & (valid_h <= 105)).sum())
    blue = int(((valid_h >= 106) & (valid_h <= 125)).sum())
    purple = int(((valid_h >= 126) & (valid_h <= 160)).sum())
    whitish = int(((s_chan < 40) & (v_chan > 170)).sum())
    total = max(1, h_chan.size)

    ratios = {
        "green": green / total,
        "cyan": cyan / total,
        "blue": blue / total,
        "purple": purple / total,
        "white": whitish / total,
    }

    candidates = []
    if ratios["purple"] > 0.08:
        candidates.append(("紫罗兰", ratios["purple"]))
    if ratios["green"] > 0.1 and ratios["green"] > ratios["cyan"]:
        candidates.append(("阳绿", ratios["green"]))
    elif ratios["green"] > 0.06:
        candidates.append(("绿色", ratios["green"]))
    if ratios["cyan"] > 0.08:
        candidates.append(("晴水", ratios["cyan"]))
    if ratios["blue"] > 0.06:
        candidates.append(("蓝水", ratios["blue"]))
    if ratios["white"] > 0.15 and not candidates:
        candidates.append(("白", ratios["white"]))

    if not candidates:
        return ""
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]


def extract_dimensions_from_text(text: str) -> tuple[str, str, str]:
    if not text:
        return "", "", ""

    water = ""
    for term, keywords in WATER_TERMS.items():
        if any(kw in text for kw in keywords):
            water = term
            break

    subject = ""
    for term, keywords in SUBJECT_TERMS.items():
        if any(kw in text for kw in keywords):
            subject = term
            break

    extras: list[str] = []
    for term, keywords in EXTRA_TERMS.items():
        if any(kw in text for kw in keywords):
            extras.append(term)

    extra = " ".join(extras) if extras else ""
    return water, subject, extra


def build_detected_full_name(color: str, water: str, subject: str, extra: str) -> str:
    parts = [p for p in [color, water, subject, extra] if p]
    return " ".join(parts)


async def apply_recognition(
    session_id: str,
    image_scores: dict[str, float] | None = None,
    text_scores: dict[str, float] | None = None,
    detected_color: str = "",
    detected_water: str = "",
    detected_subject: str = "",
    detected_extra: str = "",
) -> tuple[Product | None, float, str]:
    session = app_state.sessions.get(session_id)
    if not session:
        return None, 0.0, ""

    _decay_scores(session_id)
    bucket = _scores[session_id]

    if image_scores:
        for pid, sc in image_scores.items():
            bucket[pid] = bucket.get(pid, 0.0) + sc * IMAGE_WEIGHT
    if text_scores:
        for pid, sc in text_scores.items():
            bucket[pid] = bucket.get(pid, 0.0) + sc * TEXT_WEIGHT

    # Update detected dimensions on session
    update_fields: dict[str, Any] = {"updated_at": datetime.utcnow()}
    if detected_color:
        update_fields["detected_color"] = detected_color
    if detected_water:
        update_fields["detected_water"] = detected_water
    if detected_subject:
        update_fields["detected_subject"] = detected_subject
    if detected_extra:
        update_fields["detected_extra"] = detected_extra

    current_color = detected_color or session.detected_color
    current_water = detected_water or session.detected_water
    current_subject = detected_subject or session.detected_subject
    current_extra = detected_extra or session.detected_extra
    full_name = build_detected_full_name(current_color, current_water, current_subject, current_extra)
    if full_name and full_name != session.detected_full_name:
        update_fields["detected_full_name"] = full_name

    if len(update_fields) > 1:
        updated = session.model_copy(update=update_fields)
        app_state.sessions[session_id] = updated
        save_live_session(updated)
        await manager.broadcast(session_id, "session_status", updated.model_dump(mode="json"))

    if not bucket:
        return None, 0.0, ""

    sorted_items = sorted(bucket.items(), key=lambda kv: kv[1], reverse=True)
    top_pid, top_score = sorted_items[0]
    runner = sorted_items[1][1] if len(sorted_items) > 1 else 0.0

    product = app_state.products.get(top_pid)
    if not product:
        return None, float(top_score), ""

    sources: list[str] = []
    if image_scores and top_pid in image_scores:
        sources.append("图像")
    if text_scores and top_pid in text_scores:
        sources.append("语音")
    source_label = "+".join(sources) if sources else "历史"

    print(
        f"[REC_APP] top={product.name} score={top_score:.3f} runner={runner:.3f} "
        f"threshold={SWITCH_THRESHOLD} gap={GAP_THRESHOLD} source={source_label}"
    )

    if top_score >= SWITCH_THRESHOLD and (top_score - runner) >= GAP_THRESHOLD:
        if session.current_product_id != top_pid:
            updated = session.model_copy(
                update={"current_product_id": top_pid, "updated_at": datetime.utcnow()}
            )
            app_state.sessions[session_id] = updated
            save_live_session(updated)
            await manager.broadcast(
                session_id, "session_status", updated.model_dump(mode="json")
            )
            await manager.broadcast(
                session_id,
                "product_recognized",
                {
                    "session_id": session_id,
                    "product_id": top_pid,
                    "product_name": product.name,
                    "confidence": round(float(top_score), 3),
                    "source": source_label,
                },
            )
            _last_signal[session_id] = {
                "product_id": top_pid,
                "confidence": round(float(top_score), 3),
                "source": source_label,
            }
            print(f"[REC_SWITCH] switched to {product.name}")
        else:
            print(f"[REC_SWITCH] already on {product.name}")
    else:
        reason = []
        if top_score < SWITCH_THRESHOLD:
            reason.append(f"score<{SWITCH_THRESHOLD}")
        if (top_score - runner) < GAP_THRESHOLD:
            reason.append(f"gap<{GAP_THRESHOLD}")
        print(f"[REC_SWITCH] blocked: {' '.join(reason)}")

    return product, float(top_score), source_label


def reset_session(session_id: str) -> None:
    _scores.pop(session_id, None)
    _last_signal.pop(session_id, None)
