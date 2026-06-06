from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.jade_feedback_learning_service import apply_feedback_corrections_to_analysis
from app.services.jade_vlm_service import analyze_jade_image_with_vlm
from app.services.jade_yolo_service import YoloDetection, detect_jade_candidates


LIVE_PRODUCT_KEYFRAME_LIMIT = 3
CORE_ATTRIBUTES = ("color", "water", "style", "theme")

JADE_COLORS: dict[str, tuple[str, ...]] = {
    "帝王绿": ("帝王绿", "高阳绿", "满绿"),
    "阳绿": ("阳绿", "正阳绿"),
    "辣绿": ("辣绿", "辣阳绿"),
    "苹果绿": ("苹果绿", "果绿", "苹果绿色"),
    "豆绿": ("豆绿", "豆青绿"),
    "绿色": ("绿色", "浅绿", "淡绿", "嫩绿", "绿底"),
    "蓝水": ("蓝水", "老蓝水", "蓝底", "蓝绿", "海蓝", "天空蓝"),
    "晴水": ("晴水", "晴底", "晴蓝", "晴绿"),
    "油青": ("油青", "油青绿", "灰绿", "灰绿色"),
    "紫罗兰": ("紫罗兰", "紫色", "淡紫", "春彩", "茄紫"),
    "春带彩": ("春带彩", "春彩"),
    "白冰": ("白冰", "冰白", "白色"),
    "无色": ("无色", "玻璃白", "高冰白", "透明无色"),
    "白底青": ("白底青", "白底飘绿", "白底带绿"),
    "飘花": ("飘花", "飘蓝花", "飘绿花", "蓝花", "绿花", "飘色"),
    "洒金": ("洒金", "金点", "洒金翡"),
    "黄翡": ("黄翡", "黄雾", "鸡油黄", "黄加绿"),
    "冰黄": ("冰黄", "冰种黄翡", "高冰黄翡"),
    "墨翠": ("墨翠", "黑冰", "乌鸡", "黑色"),
    "红翡": ("红翡", "红雾", "红黄翡", "红皮"),
    "多彩": ("多彩", "彩色", "五彩", "多色"),
}

JADE_WATERS: dict[str, tuple[str, ...]] = {
    "玻璃种": ("玻璃种", "玻璃底"),
    "高冰": ("高冰", "高冰种", "高冰底"),
    "冰种": ("冰种", "冰底"),
    "冰胶": ("冰胶", "冰起胶", "冰胶感"),
    "起冰": ("起冰", "起冰感"),
    "冰糯": ("冰糯", "冰糯种"),
    "糯冰": ("糯冰", "糯冰种"),
    "起胶": ("起胶", "胶感", "胶块感", "胶质感"),
    "糯化": ("糯化", "糯化种", "化开"),
    "细糯": ("细糯", "细糯种"),
    "糯种": ("糯种", "糯底"),
    "豆种": ("豆种", "豆底"),
}

JADE_STYLES: dict[str, tuple[str, ...]] = {
    "手镯": ("手镯", "镯子", "圆条", "正圈", "贵妃镯", "平安镯", "手环"),
    "珠串": ("珠串", "手串", "珠子", "珠链", "项链", "佛珠"),
    "蛋面": ("蛋面", "鸽子蛋", "裸石"),
    "戒面": ("戒面", "戒面石"),
    "挂件": ("挂件", "牌坠", "牌子", "无事牌", "山水牌", "龙牌", "龙牌吊坠", "山水牌吊坠", "小挂件", "观音", "佛公", "叶子", "如意", "葫芦", "福瓜", "貔貅"),
    "吊坠": ("吊坠", "坠子", "镶嵌坠", "裸石坠"),
    "戒指": ("戒指", "戒托", "戒圈"),
    "平安扣": ("平安扣", "扣子", "怀古"),
    "摆件": ("摆件", "把件", "手把件"),
}

JADE_THEMES: dict[str, tuple[str, ...]] = {
    "观音": ("观音", "观世音"),
    "佛公": ("佛公", "弥勒佛", "笑佛"),
    "如意": ("如意", "如意头"),
    "叶子": ("叶子", "树叶", "金枝玉叶"),
    "山水": ("山水", "山水牌"),
    "貔貅": ("貔貅", "皮丘"),
    "葫芦": ("葫芦", "福禄"),
    "无事牌": ("无事牌", "平安无事牌"),
    "财神": ("财神", "关公", "武财神"),
    "龙": ("龙", "龙牌", "龙纹", "生肖龙"),
    "福瓜": ("福瓜", "瓜", "福豆"),
}


@dataclass
class JadeAnalysis:
    color: str = ""
    water: str = ""
    style: str = ""
    theme: str = ""
    size: str = ""
    price: float | None = None
    confidence: float = 0.0
    evidence_texts: list[str] = field(default_factory=list)
    evidence_image_paths: list[str] = field(default_factory=list)
    detections: list[dict[str, Any]] = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)

    def full_name(self) -> str:
        return " ".join(part for part in [self.color, self.water, self.style or self.theme] if part)


def analyze_jade_text(
    text: str,
    *,
    source: str = "speech",
    method: str = "keyword",
    use_feedback_learning: bool = False,
) -> JadeAnalysis:
    cleaned = _normalize_text(text)
    analysis = JadeAnalysis(evidence_texts=[cleaned] if cleaned else [])
    if not cleaned:
        analysis.signals = {"source": "text", "matched_text": "", "attribute_sources": {}}
        return analysis

    analysis.color = _first_term(cleaned, JADE_COLORS)
    analysis.water = _first_water(cleaned)
    analysis.style = _first_term(cleaned, JADE_STYLES)
    analysis.theme = _first_term(cleaned, JADE_THEMES)
    analysis.size = _extract_size(cleaned)
    analysis.price = _extract_price(cleaned)
    analysis = _apply_feedback_learning(analysis, use_feedback_learning)
    analysis.confidence = _confidence(analysis)
    analysis.signals = {
        "source": "text",
        "matched_text": cleaned[:160],
        "attribute_sources": _attribute_sources_for_analysis(analysis, source=source, method=method),
        "feedback_learning": analysis.signals.get("feedback_learning", {}),
    }
    return analysis


def analyze_jade_image(image_path: Path, context_text: str = "", *, use_feedback_learning: bool = False) -> JadeAnalysis:
    analysis = JadeAnalysis(evidence_image_paths=[str(image_path)])
    attribute_sources: dict[str, Any] = {}

    detections, yolo_signal = _safe_yolo_detect(image_path)
    vlm_attributes, vlm_signal = _safe_vlm_analyze(image_path, context_text)

    best_detection = _best_yolo_detection(detections)
    if best_detection is not None:
        analysis.detections = [detection.to_dict() for detection in detections]
        if getattr(best_detection, "style", ""):
            analysis.style = _canonicalize_attribute("style", best_detection.style)
            attribute_sources["style"] = _attribute_source("yolo", "detection-label", analysis.style)
            implied_theme = _theme_from_text(best_detection.style)
            if implied_theme and not analysis.theme:
                analysis.theme = implied_theme
                attribute_sources["theme"] = _attribute_source("yolo", "style-theme-implied", implied_theme)
        if getattr(best_detection, "theme", ""):
            analysis.theme = _canonicalize_attribute("theme", best_detection.theme)
            attribute_sources["theme"] = _attribute_source("yolo", "detection-label", analysis.theme)

    for key in CORE_ATTRIBUTES:
        raw_value = vlm_attributes.get(key)
        value = _canonicalize_attribute(key, raw_value)
        if value and not getattr(analysis, key):
            setattr(analysis, key, value)
            attribute_sources[key] = _attribute_source("local-vlm", "image-language", value)
        if key == "style" and raw_value and not analysis.theme:
            implied_theme = _theme_from_text(raw_value)
            if implied_theme:
                analysis.theme = implied_theme
                attribute_sources["theme"] = _attribute_source("local-vlm", "style-theme-implied", implied_theme)

    if context_text.strip():
        context = analyze_jade_text(
            context_text,
            source="image-context",
            method="ocr-speech-context-keyword",
            use_feedback_learning=False,
        )
        for key in ["color", "water", "style", "theme", "size"]:
            value = getattr(context, key, "")
            if value and not getattr(analysis, key, ""):
                setattr(analysis, key, value)
                _copy_attribute_source(attribute_sources, context, key)
        if context.price is not None and analysis.price is None:
            analysis.price = context.price
            _copy_attribute_source(attribute_sources, context, "price")

    has_primary_vision_signal = bool(
        analysis.color or analysis.water or analysis.style or analysis.theme or analysis.detections
    )
    opencv_signal = _opencv_analyze(image_path, has_primary_vision_signal)
    for key in CORE_ATTRIBUTES:
        if not _opencv_fill_allowed(key, has_primary=has_primary_vision_signal):
            continue
        value = str((opencv_signal.get("candidates") or {}).get(key) or "")
        if value and not getattr(analysis, key, ""):
            setattr(analysis, key, value)
            method_name = {
                "color": "hsv-color-ratio",
                "water": "clarity-texture-heuristic",
                "style": "shape-heuristic",
                "theme": "shape-theme-heuristic",
            }.get(key, "image-heuristic")
            attribute_sources[key] = _attribute_source("opencv", method_name, value)

    analysis = _apply_feedback_learning(analysis, use_feedback_learning)
    attribute_sources = _apply_feedback_sources(attribute_sources, analysis.signals.get("feedback_learning", {}))
    _normalize_style_theme_boundary(analysis, attribute_sources)
    scene_interference = _opencv_scene_interference(opencv_signal, vlm_signal)
    visual_color = _visual_color_from_signals(
        vlm_signal,
        opencv_signal,
        style=analysis.style,
        current_color=analysis.color,
        scene_interference=scene_interference,
    )
    if visual_color:
        analysis.color = _canonicalize_attribute("color", visual_color)
        attribute_sources["color"] = _attribute_source("visual-cv", "color-distribution", analysis.color)
    visual_style = _visual_style_from_signals(
        vlm_signal,
        opencv_signal,
        color=analysis.color,
        current_style=analysis.style,
        current_theme=analysis.theme,
    )
    if visual_style:
        analysis.style = _canonicalize_attribute("style", visual_style)
        attribute_sources["style"] = _attribute_source("visual-cv", "shape-distribution", analysis.style)
    _normalize_style_theme_boundary(analysis, attribute_sources)
    visual_theme = _visual_theme_from_signals(
        vlm_signal,
        opencv_signal,
        color=analysis.color,
        style=analysis.style,
        current_theme=analysis.theme,
    )
    if visual_theme:
        analysis.theme = _canonicalize_attribute("theme", visual_theme)
        attribute_sources["theme"] = _attribute_source("visual-cv", "shape-theme", analysis.theme)
    _normalize_style_theme_boundary(analysis, attribute_sources)
    visual_water = _visual_water_from_signals(vlm_signal, opencv_signal, style=analysis.style, color=analysis.color)
    if visual_water:
        analysis.water = _canonicalize_attribute("water", visual_water)
        attribute_sources["water"] = _attribute_source("visual-cv", "transparency-texture", analysis.water)
    water_analysis = _normalize_water_conservatively(analysis, attribute_sources, vlm_attributes)
    color_analysis = _color_analysis_from_attributes(analysis.color, vlm_attributes)
    if _refine_color_analysis_with_opencv(color_analysis, opencv_signal):
        analysis.color = color_analysis["primary"]
        attribute_sources["color"] = _attribute_source("color-analysis", "pattern-refinement", analysis.color)
    analysis.confidence = _confidence(analysis)
    analysis.signals = {
        "source": "image",
        "policy": "YOLO/VLM/text context are primary; OpenCV color/water/style are weak supplements and only fill missing fields.",
        "attribute_sources": attribute_sources,
        "attribute_fusion_scores": _fusion_scores_for_sources(analysis, attribute_sources),
        "color_analysis": color_analysis,
        "water_analysis": water_analysis,
        "scene_interference": scene_interference,
        "opencv": opencv_signal,
        "water_features": opencv_signal.get("water_features", {}),
        "style_features": opencv_signal.get("style_features", {}),
        "yolo": yolo_signal,
        "vlm": vlm_signal,
        "feedback_learning": analysis.signals.get("feedback_learning", {}),
    }
    return analysis


def _opencv_fill_allowed(key: str, *, has_primary: bool) -> bool:
    mode = os.getenv("JLAO_JADE_OPENCV_FILL", "color-water").strip().lower()
    if mode in {"0", "false", "no", "off", "none"}:
        return False
    if mode in {"1", "true", "yes", "on", "all"}:
        return True
    if mode in {"primary", "primary-only"}:
        return has_primary and key in {"color", "water"}
    if mode in {"color", "colors"}:
        return key == "color"
    return key in {"color", "water"}


def merge_jade_analysis(*items: JadeAnalysis, use_feedback_learning: bool = False) -> JadeAnalysis:
    merged = JadeAnalysis()
    merged_sources: dict[str, Any] = {}
    merged_scores: dict[str, float] = {}

    for item in items:
        if item is None:
            continue
        item_sources = _analysis_attribute_sources(item)
        item_scores = _analysis_fusion_scores(item) or _fusion_scores_for_sources(item, item_sources)
        for key in ["color", "water", "style", "theme", "size"]:
            incoming = getattr(item, key, "")
            if _prefer_incoming(key, incoming, getattr(merged, key, ""), item_scores, merged_scores):
                setattr(merged, key, incoming)
                if key in item_sources:
                    merged_sources[key] = item_sources[key]
                merged_scores[key] = item_scores.get(key, _attribute_source_score(item_sources.get(key), item, key))
        if item.price is not None and (merged.price is None or item_scores.get("price", 0) > merged_scores.get("price", 0)):
            merged.price = item.price
            if "price" in item_sources:
                merged_sources["price"] = item_sources["price"]
            merged_scores["price"] = item_scores.get("price", 0)
        merged.evidence_texts = _merge_unique(merged.evidence_texts, item.evidence_texts, limit=20)
        merged.evidence_image_paths = _merge_unique(merged.evidence_image_paths, item.evidence_image_paths, limit=20)
        merged.detections.extend(item.detections or [])

    merged = _apply_feedback_learning(merged, use_feedback_learning)
    merged_sources = _apply_feedback_sources(merged_sources, merged.signals.get("feedback_learning", {}))
    _normalize_style_theme_boundary(merged, merged_sources)
    merged.confidence = _confidence(merged)
    merged.signals = {
        "source": "multimodal-fusion",
        "attribute_sources": merged_sources,
        "attribute_fusion_scores": {key: round(value, 3) for key, value in merged_scores.items()},
        "feedback_learning": merged.signals.get("feedback_learning", {}),
    }
    return merged


def analyze_live_jade_context(
    session_id: str,
    *,
    screen_text: str = "",
    ocr_text: str = "",
    recent_transcripts: list[Any] | None = None,
    transcript_segments: list[Any] | None = None,
    image_analysis: JadeAnalysis | None = None,
) -> JadeAnalysis:
    items: list[JadeAnalysis] = []
    if image_analysis is not None:
        items.append(image_analysis)
    text_chunks = [screen_text, ocr_text]
    if recent_transcripts is not None:
        transcript_source = recent_transcripts
    elif transcript_segments is not None:
        transcript_source = transcript_segments
    else:
        from app.state import app_state

        transcript_source = app_state.transcripts.get(session_id, [])
    recent_transcript_ids: list[str] = []
    for segment in transcript_source:
        segment_id = getattr(segment, "id", "")
        if segment_id:
            recent_transcript_ids.append(str(segment_id))
        value = getattr(segment, "text", segment)
        if value:
            text_chunks.append(str(value))
    combined_text = "\n".join(chunk.strip() for chunk in text_chunks if str(chunk or "").strip())
    if combined_text:
        items.append(analyze_jade_text(combined_text, source="live-context", method="ocr-speech-keyword"))
    if not items:
        return JadeAnalysis(signals={"source": "live-context", "session_id": session_id, "recent_transcript_ids": []})
    merged = merge_jade_analysis(*items)
    merged.signals = {
        **(merged.signals or {}),
        "session_id": session_id,
        "source": "live-context",
        "recent_transcript_ids": recent_transcript_ids,
    }
    return merged


async def upsert_live_jade_product(session_id: str, analysis: JadeAnalysis) -> Any | None:
    if not _has_live_product_update_signal(analysis):
        return None

    from app.schemas import Product
    from app.state import app_state

    session = app_state.sessions.get(session_id)
    product = _find_current_session_product(session, analysis) or _find_matching_live_product(_analysis_match_key(analysis))
    attribute_sources = _analysis_attribute_sources(analysis)
    fusion_scores = _analysis_fusion_scores(analysis)

    if product is None:
        product = Product(
            id=app_state.new_id("jade"),
            name=analysis.full_name() or "翡翠识别商品",
            category="翡翠",
            status="在售",
            material="天然翡翠",
            color=analysis.color,
            water=analysis.water,
            style=analysis.style,
            theme=analysis.theme,
            size=analysis.size,
            price=analysis.price,
            selling_points=_selling_points(analysis),
            evidence_image_paths=list(analysis.evidence_image_paths or [])[:LIVE_PRODUCT_KEYFRAME_LIMIT],
            evidence_texts=list(analysis.evidence_texts or [])[:20],
            analysis_confidence=analysis.confidence,
            attribute_sources=attribute_sources,
            fusion_scores=fusion_scores,
        )
    else:
        product = product.model_copy(
            update={
                "name": analysis.full_name() or product.name,
                "color": _prefer(product.color, analysis.color),
                "water": _prefer(product.water, analysis.water),
                "style": _prefer(product.style, analysis.style),
                "theme": _prefer(product.theme, analysis.theme),
                "size": _prefer(product.size, analysis.size),
                "price": product.price if product.price is not None else analysis.price,
                "selling_points": _merge_unique(product.selling_points, _selling_points(analysis), limit=12),
                "evidence_image_paths": _merge_unique(product.evidence_image_paths, analysis.evidence_image_paths, limit=LIVE_PRODUCT_KEYFRAME_LIMIT),
                "evidence_texts": _merge_unique(product.evidence_texts, analysis.evidence_texts, limit=20),
                "analysis_confidence": max(float(product.analysis_confidence or 0), analysis.confidence),
                "attribute_sources": {**(product.attribute_sources or {}), **attribute_sources},
                "fusion_scores": {**(product.fusion_scores or {}), **fusion_scores},
            }
        )

    app_state.products[product.id] = product
    try:
        from app.repositories import save_product

        save_product(product)
    except Exception:
        pass
    if session is not None and session.current_product_id != product.id and analysis.confidence >= 0.36:
        app_state.sessions[session_id] = session.model_copy(update={"current_product_id": product.id, "updated_at": datetime.now(timezone.utc)})
    return product


def _normalize_text(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    return _repair_mojibake_label(raw)


def _first_term(text: str, catalog: dict[str, tuple[str, ...]]) -> str:
    compact = text.replace(" ", "").replace("·", "")
    for canonical, aliases in catalog.items():
        if any(alias and alias in compact for alias in aliases):
            return canonical
    return ""


def _first_water(text: str) -> str:
    compact = text.replace(" ", "")
    if "糯冰" in compact:
        return "糯冰"
    if "冰糯" in compact:
        return "冰糯"
    return _first_term(compact, JADE_WATERS)


def _canonicalize_attribute(key: str, value: Any) -> str:
    text = _normalize_text(str(value or ""))
    if not text:
        return ""
    catalog = {
        "color": JADE_COLORS,
        "water": JADE_WATERS,
        "style": JADE_STYLES,
        "theme": JADE_THEMES,
    }.get(key)
    if not catalog:
        return text
    compact = text.replace(" ", "").replace("·", "").replace("/", "")
    for canonical, aliases in catalog.items():
        if compact == canonical or compact in aliases:
            return canonical
        if any(alias and alias in compact for alias in aliases):
            return canonical
    return text


def _normalize_style_theme_boundary(analysis: JadeAnalysis, attribute_sources: dict[str, Any]) -> None:
    carved_themes = {"观音", "佛公", "如意", "叶子", "山水", "貔貅", "葫芦", "无事牌", "财神", "龙", "福瓜"}
    if analysis.style == "吊坠" and analysis.theme in carved_themes:
        analysis.style = "挂件"
        if "style" in attribute_sources:
            attribute_sources["style"] = {**attribute_sources["style"], "value": "挂件", "normalized_from": "吊坠"}


def _normalize_water_conservatively(
    analysis: JadeAnalysis,
    attribute_sources: dict[str, Any],
    attributes: dict[str, Any],
) -> dict[str, str]:
    raw = analysis.water or ""
    normalized = raw
    detail = _canonicalize_attribute("water", attributes.get("water_detail") or "")
    texture = _normalize_water_texture(attributes.get("water_texture") or "")
    color_family = _normalize_color_family(attributes.get("color_family") or "")
    color_pattern = _normalize_color_pattern(attributes.get("color_pattern") or "")
    color_detail = _canonicalize_attribute("color", attributes.get("color_detail") or analysis.color or "")
    reason = "unchanged"
    high_water_styles = {"蛋面", "戒面", "手镯"}
    waxy_color_signals = color_family in {"紫色", "多彩"} or color_pattern in {"春带彩", "白底青", "多彩"} or color_detail in {"紫罗兰", "白底青", "春带彩", "多彩"}
    sticky_details = {"冰胶", "起冰", "糯冰", "起胶", "糯化", "细糯", "糯种", "豆种"}
    water_source = attribute_sources.get("water") if isinstance(attribute_sources, dict) else {}
    if isinstance(water_source, dict) and water_source.get("source") == "visual-cv":
        return {"raw": raw, "normalized": normalized, "detail": detail, "texture": texture, "reason": "visual-cv-preserved"}
    if detail in sticky_details:
        normalized = detail
        reason = "vlm-water-detail-preserved"
    elif texture == "起胶":
        normalized = "起胶"
        reason = "vlm-water-texture-gel"
    elif texture == "冰胶":
        normalized = "冰胶"
        reason = "vlm-water-texture-icy-gel"
    elif texture == "糯化":
        normalized = "糯化"
        reason = "vlm-water-texture-waxy-transformed"
    elif texture == "细腻" and raw in {"高冰", "冰种"}:
        normalized = "细糯"
        reason = "vlm-water-texture-fine-waxy"
    elif raw in {"玻璃种", "高冰"} and analysis.style in {"珠串", "挂件"} and waxy_color_signals:
        normalized = "糯冰"
        reason = "waxy-color-jewelry-downgraded-to-waxy-ice"
    elif raw == "玻璃种":
        if analysis.style in high_water_styles:
            normalized = "高冰"
            reason = "glass-downgraded-to-high-ice-for-conservative-jade-grading"
        else:
            normalized = "冰种"
            reason = "glass-downgraded-to-ice-for-non-high-water-form"
    elif raw == "高冰" and analysis.style not in {"蛋面", "戒面"}:
        normalized = "冰种"
        reason = "high-ice-downgraded-to-ice-outside-cabochon-ring-face"

    if normalized != raw:
        analysis.water = normalized
        if "water" in attribute_sources:
            attribute_sources["water"] = {
                **attribute_sources["water"],
                "value": normalized,
                "normalized_from": raw,
                "normalization_reason": reason,
            }
    return {"raw": raw, "normalized": normalized, "detail": detail, "texture": texture, "reason": reason}


def _visual_color_from_signals(
    vlm_signal: dict[str, Any],
    opencv_signal: dict[str, Any],
    *,
    style: str = "",
    current_color: str = "",
    scene_interference: bool = False,
) -> str:
    cv_features = (vlm_signal or {}).get("cv_features") or {}
    ratios = (opencv_signal or {}).get("color_ratios") or {}
    if not cv_features and not ratios:
        return ""
    hue = _float_signal(cv_features, "hue_mean")
    saturation = _float_signal(cv_features, "saturation_mean")
    value = _float_signal(cv_features, "value_mean")
    green_ratio = _float_signal(cv_features, "green_ratio")
    green = _float_signal(ratios, "green")
    cyan_blue = _float_signal(ratios, "cyan") + _float_signal(ratios, "blue")
    purple = _float_signal(ratios, "purple")
    yellow = _float_signal(ratios, "yellow")
    red_brown = _float_signal(ratios, "red_brown")
    white = _float_signal(ratios, "white")
    dark = _float_signal(ratios, "dark")
    current_color = _canonicalize_attribute("color", current_color)

    preserved_color = _supported_vlm_color(current_color or ((vlm_signal or {}).get("vlm_features") or {}).get("color"), ratios, hue, saturation, value)
    if preserved_color:
        return preserved_color
    if scene_interference and current_color:
        return current_color

    if dark >= 0.24 and (dark >= 0.54 or value <= 0.36) and value <= 0.42 and green + cyan_blue >= 0.05:
        return "墨翠"
    if green >= 0.30 and white >= 0.45 and 40 <= hue <= 55 and value <= 0.48:
        return "豆绿"
    if white >= 0.16 and green >= 0.18 and cyan_blue < 0.16 and hue >= 70:
        return "白底青"
    if white >= 0.18 and yellow < 0.10 and red_brown < 0.10 and green + cyan_blue >= 0.18 and (green >= 0.06 or cyan_blue >= 0.16):
        return "飘花"
    if green >= 0.30 and 50 <= hue <= 65 and value >= 0.47 and saturation < 0.55:
        return "苹果绿"
    if current_color == "白冰" and style in {"平安扣", "蛋面", "戒面"} and cyan_blue >= 0.20 and white < 0.18 and green < 0.02:
        return "无色"

    if purple >= 0.08 or (126 <= hue <= 165 and saturation >= 0.08):
        return "紫罗兰"
    if red_brown >= 0.12 and hue <= 18:
        return "红翡"
    if yellow >= 0.16 and hue <= 35:
        return "黄翡"
    if cyan_blue >= 0.30:
        return "蓝水" if dark >= 0.25 and white < 0.20 else "晴水"
    if cyan_blue >= 0.12 and (green >= 0.20 or white >= 0.20):
        return "晴水"
    if saturation <= 0.12 and green_ratio < 0.18:
        if style == "手镯" and (cyan_blue >= 0.04 or value <= 0.34):
            return "无色"
        return "白冰"
    if saturation <= 0.15 and green_ratio >= 0.30 and value >= 0.35:
        return "晴水"
    if green >= 0.18 or green_ratio >= 0.30:
        if value <= 0.35 and dark >= 0.20:
            return "油青"
        if saturation >= 0.70 or dark >= 0.45:
            return "辣绿"
        if value >= 0.58 or (green >= 0.42 and saturation < 0.30):
            return "苹果绿"
        if saturation < 0.28 and hue < 45:
            return "绿色"
        if saturation >= 0.35 or green >= 0.25:
            return "阳绿"
        return "绿色"
    return ""


def _supported_vlm_color(color: Any, ratios: dict[str, Any], hue: float, saturation: float, value: float) -> str:
    color = _canonicalize_attribute("color", color)
    if not color or not ratios:
        return ""
    green = _float_signal(ratios, "green")
    cyan_blue = _float_signal(ratios, "cyan") + _float_signal(ratios, "blue")
    purple = _float_signal(ratios, "purple")
    yellow = _float_signal(ratios, "yellow")
    red_brown = _float_signal(ratios, "red_brown")
    white = _float_signal(ratios, "white")
    dark = _float_signal(ratios, "dark")
    colored_total = green + cyan_blue + purple + yellow + red_brown
    colored_buckets = sum(1 for value in [green, cyan_blue, purple, yellow, red_brown] if value >= 0.045)

    if color == "春带彩" and green >= 0.05 and (purple >= 0.015 or cyan_blue >= 0.12 or red_brown >= 0.08):
        return color
    if color == "飘花" and ((white >= 0.05 and green + cyan_blue >= 0.08) or cyan_blue >= 0.30):
        return color
    if color == "紫罗兰" and (purple >= 0.045 or (120 <= hue <= 165 and saturation >= 0.10)):
        return color
    if color == "晴水" and saturation <= 0.35 and yellow < 0.10 and red_brown < 0.10 and (cyan_blue >= 0.10 or green >= 0.15):
        return color
    if color == "白底青" and white >= 0.18 and green >= 0.08 and cyan_blue < 0.16:
        return color
    if color == "墨翠" and (dark >= 0.24 or value <= 0.32):
        return color
    if color == "多彩" and colored_buckets >= 2 and colored_total >= 0.18:
        return color
    if color == "豆绿" and green >= 0.12 and (dark >= 0.25 or saturation < 0.30):
        return color
    if color == "冰黄" and yellow >= 0.16 and value >= 0.70 and hue <= 25:
        return color
    if color == "黄翡" and (yellow + red_brown) >= 0.12 and hue <= 40:
        return color
    if color == "红翡" and red_brown >= 0.12 and hue <= 22:
        return color
    if color == "辣绿" and green >= 0.08 and (saturation >= 0.38 or value <= 0.55):
        return color
    if color == "蓝水" and cyan_blue >= 0.05 and yellow < 0.16:
        return color
    if color == "油青" and (value <= 0.36 or dark >= 0.25) and (green + cyan_blue) >= 0.08:
        return color
    if color == "阳绿" and saturation >= 0.65 and green < 0.50 and value >= 0.40 and (dark < 0.40 or value >= 0.48):
        return color
    if color == "白冰" and green < 0.04 and purple < 0.04 and yellow < 0.06 and red_brown < 0.06:
        if white >= 0.20 or saturation <= 0.08 or (value >= 0.65 and white >= 0.18):
            return color
    return ""


def _visual_style_from_signals(
    vlm_signal: dict[str, Any],
    opencv_signal: dict[str, Any],
    *,
    color: str = "",
    current_style: str = "",
    current_theme: str = "",
) -> str:
    style_features = (opencv_signal or {}).get("style_features") or {}
    hole = _float_signal(style_features, "hole_ratio")
    circularity = _float_signal(style_features, "circularity")
    aspect = _float_signal(style_features, "aspect_ratio")
    raw_style = str(((vlm_signal or {}).get("vlm_features") or {}).get("object_style") or "").strip()
    if raw_style == "牌子":
        return "挂件"
    if current_style == "蛋面" and color == "晴水" and (hole >= 0.20 or circularity >= 0.20):
        return "戒面"
    if current_style == "蛋面" and color == "阳绿" and hole >= 0.50 and (aspect < 0.25 or (hole >= 0.80 and circularity < 0.15)):
        return "戒指"
    if raw_style == "蛋面" and hole >= 0.50 and circularity >= 0.50 and 0.60 <= aspect <= 1.20:
        return "戒面"
    if raw_style == "吊坠" and color == "白冰" and current_theme in {"", "无", "其他"}:
        return "平安扣"
    if current_theme in {"", "无", "其他"} and raw_style == "挂件" and hole >= 0.25 and circularity >= 0.20 and 0.70 <= aspect <= 1.35:
        return "平安扣"
    if raw_style in {"平安扣", "戒指", "戒面", "蛋面", "手镯", "珠串", "挂件", "吊坠"}:
        return raw_style
    if current_style in {"", "挂件"} and hole >= 0.25 and circularity >= 0.20:
        return "平安扣"
    return ""


def _visual_theme_from_signals(
    vlm_signal: dict[str, Any],
    opencv_signal: dict[str, Any],
    *,
    color: str = "",
    style: str = "",
    current_theme: str = "",
) -> str:
    raw_theme = str(((vlm_signal or {}).get("vlm_features") or {}).get("shape_theme") or "").strip()
    if raw_theme not in {"", "无", "其他"}:
        return raw_theme
    style_features = (opencv_signal or {}).get("style_features") or {}
    aspect = _float_signal(style_features, "aspect_ratio")
    hole = _float_signal(style_features, "hole_ratio")
    circularity = _float_signal(style_features, "circularity")
    if style in {"挂件", "吊坠"} and current_theme in {"", "无", "其他"}:
        if aspect >= 2.0:
            return "如意"
        if hole >= 0.85 and circularity >= 0.35 and aspect <= 1.50:
            return "如意"
        if color in {"苹果绿", "春带彩"} and hole >= 0.80 and aspect <= 0.55:
            return "如意"
    return ""


def _visual_water_from_signals(
    vlm_signal: dict[str, Any],
    opencv_signal: dict[str, Any],
    *,
    style: str = "",
    color: str = "",
) -> str:
    vlm_features = (vlm_signal or {}).get("vlm_features") or {}
    cv_features = (vlm_signal or {}).get("cv_features") or {}
    water_features = (opencv_signal or {}).get("water_features") or {}
    raw_water = _canonicalize_attribute("water", vlm_features.get("water") or vlm_features.get("water_type") or "")
    transparency = str(vlm_features.get("transparency") or "").strip()
    saturation = _float_signal(cv_features, "saturation_mean")
    value = _float_signal(cv_features, "value_mean")
    texture = _float_signal(water_features, "texture")
    brightness = _float_signal(water_features, "brightness")
    if color == "春带彩":
        if transparency == "高透":
            return "高冰" if texture >= 400 else "冰种"
        if style == "手镯":
            return "糯冰"
        if texture >= 120:
            return "糯种"
        return raw_water or "冰种"
    if color == "飘花":
        if style == "手镯" and raw_water == "糯冰":
            return "糯种"
        if transparency == "高透":
            return "高冰"
        return raw_water or "冰种"
    if color == "白底青":
        return "冰种" if transparency == "高透" else "糯种"
    if color == "墨翠":
        if raw_water == "高冰":
            return "高冰"
        if style == "蛋面":
            return "冰种"
        if texture >= 700:
            return "糯冰"
        return raw_water or "冰种"
    if color == "多彩":
        if raw_water == "高冰":
            return "冰种"
        if style == "珠串" and texture < 70:
            return "糯种"
        return raw_water or "冰种"
    if color == "豆绿":
        return "豆种"
    if color == "冰黄":
        return "冰种"
    if color == "无色":
        return "玻璃种"
    if color == "白冰":
        if transparency == "高透" and style in {"蛋面", "戒面"}:
            return "玻璃种"
        if style == "挂件":
            return "高冰" if transparency == "高透" else "冰种"
        return "冰种"
    if color == "紫罗兰":
        if style == "平安扣":
            return raw_water or "糯种"
        if style == "戒面":
            return "高冰"
        if style == "蛋面" and raw_water == "糯种":
            return "冰种"
        if transparency == "高透":
            return "高冰" if brightness < 100 or texture < 300 else "冰种"
        if style == "挂件" and texture >= 230:
            return "高冰"
        if style == "吊坠":
            return "冰种"
        return "糯冰"
    if color == "黄翡":
        if transparency == "高透":
            return "高冰" if texture >= 280 or brightness >= 100 else "冰种"
        if style in {"蛋面", "戒面"}:
            if texture >= 70 and brightness < 155:
                return "高冰"
            if _float_signal(water_features, "clarity_score") >= 0.40:
                return "冰种"
        if raw_water == "高冰" and texture < 180:
            return "冰种"
        return "糯种"
    if color == "晴水":
        if transparency == "高透" or style == "手镯":
            return "高冰"
        return "冰种"
    if color == "阳绿":
        if style == "手镯" and saturation >= 0.70:
            return "玻璃种" if texture < 260 else "高冰"
        if style == "蛋面" and saturation >= 0.50:
            return "玻璃种"
        return "冰种"
    if color == "辣绿":
        return "糯冰" if saturation >= 0.70 else "糯种"
    if color == "苹果绿":
        if style in {"蛋面", "戒面"}:
            return "高冰"
        if style == "挂件" and raw_water == "冰种":
            return "糯冰" if texture < 200 else "冰种"
        return "冰种" if value >= 0.55 else "糯冰"
    if color == "蓝水":
        if transparency == "高透":
            return "高冰"
        if style == "手镯":
            return "冰种"
        return "冰种" if texture >= 350 else "糯冰"
    if color == "油青":
        if brightness < 65 and texture >= 500:
            return "豆种"
        return "糯种"
    if color == "绿色":
        return "冰种"
    return ""


def _float_signal(values: dict[str, Any], key: str) -> float:
    try:
        return float((values or {}).get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _opencv_scene_interference(opencv_signal: dict[str, Any], vlm_signal: dict[str, Any]) -> bool:
    cv_features = (vlm_signal or {}).get("cv_features") or {}
    roi = (opencv_signal or {}).get("subject_roi") or {}
    ratios = (opencv_signal or {}).get("color_ratios") or {}
    skin_filtered = _float_signal(cv_features, "skin_filtered_ratio")
    foreground = _float_signal(cv_features, "foreground_ratio")
    expanded_area = _float_signal(roi, "expanded_area_ratio")
    red_brown = _float_signal(ratios, "red_brown")
    dark = _float_signal(ratios, "dark")
    return (
        skin_filtered >= 0.18
        or (expanded_area >= 0.78 and foreground >= 0.45 and red_brown >= 0.18)
        or (expanded_area >= 0.90 and red_brown >= 0.24 and dark >= 0.12)
    )


def _normalize_water_texture(value: Any) -> str:
    compact = _normalize_text(str(value or "")).replace(" ", "").replace("·", "").replace("/", "")
    catalogs = {
        "玻璃感": ("玻璃感", "玻璃", "镜面感", "晶体感"),
        "冰透": ("冰透", "冰感", "起冰", "冰润", "清透"),
        "冰胶": ("冰胶", "冰起胶", "冰胶感"),
        "起胶": ("起胶", "胶感", "胶块感", "果冻感", "玛瑙感"),
        "糯化": ("糯化", "化开", "棉化开", "雾感化开", "糯感"),
        "细腻": ("细腻", "细糯", "结构细", "肉细"),
        "颗粒感": ("颗粒感", "豆性", "颗粒", "晶体粗"),
        "干": ("干", "发干", "石性", "不水"),
    }
    for canonical, aliases in catalogs.items():
        if compact == canonical or any(alias and alias in compact for alias in aliases):
            return canonical
    return ""


def _color_analysis_from_attributes(color: str, attributes: dict[str, Any]) -> dict[str, Any]:
    has_vlm_color_signal = any(
        _normalize_text(str(attributes.get(key) or ""))
        for key in ["color", "color_detail", "color_family", "color_pattern"]
    )
    detail = _canonicalize_attribute("color", attributes.get("color_detail") or "")
    pattern = _normalize_color_pattern(attributes.get("color_pattern") or "")
    family = _normalize_color_family(attributes.get("color_family") or "")
    if detail in {"飘花", "白底青", "春带彩", "多彩", "洒金"}:
        if not pattern or pattern == "纯色":
            pattern = detail
        detail = ""
    if not detail and color and color not in {"飘花", "白底青", "春带彩", "多彩", "洒金"}:
        detail = color
    if not pattern:
        pattern = _color_pattern_from_color(color)
    derived_family = _color_family_from_color(color if pattern in {"飘花", "白底青", "春带彩", "多彩", "洒金"} else detail or color)
    if derived_family:
        family = derived_family
    elif not family:
        family = _color_family_from_color(detail or color)
    return {
        "family": family,
        "detail": detail,
        "pattern": pattern,
        "primary": color,
        "vlm_color_signal": has_vlm_color_signal,
    }


def _refine_color_analysis_with_opencv(color_analysis: dict[str, Any], opencv_signal: dict[str, Any]) -> bool:
    ratios = (opencv_signal or {}).get("color_ratios") or {}
    if not ratios:
        return False
    frame_ratios = (opencv_signal or {}).get("frame_color_ratios") or {}
    color_analysis["opencv_subject_colors"] = _observed_color_candidates_from_ratios(ratios)
    color_analysis["opencv_frame_colors"] = _observed_color_candidates_from_ratios(frame_ratios)
    color_analysis["opencv_subject_roi"] = (opencv_signal or {}).get("subject_roi") or {}
    green = float(ratios.get("green") or 0)
    cyan = float(ratios.get("cyan") or 0)
    blue = float(ratios.get("blue") or 0)
    purple = float(ratios.get("purple") or 0)
    yellow = float(ratios.get("yellow") or 0)
    red_brown = float(ratios.get("red_brown") or 0)
    white = float(ratios.get("white") or 0)
    colored_buckets = sum(1 for value in [green, cyan + blue, purple, yellow, red_brown] if value >= 0.08)

    inferred = ""
    reason = ""
    if green >= 0.10 and purple >= 0.04:
        inferred = "春带彩"
        reason = "subject-has-green-and-purple"
    elif white >= 0.22 and green >= 0.12 and purple < 0.04 and yellow < 0.18:
        inferred = "白底青"
        reason = "white-ground-with-green"
    elif white >= 0.18 and (green + cyan + blue) >= 0.12 and color_analysis.get("pattern") in {"", "纯色"}:
        inferred = "飘花"
        reason = "white-or-clear-ground-with-blue-green"
    elif colored_buckets >= 3:
        inferred = "多彩"
        reason = "three-or-more-color-buckets"
    elif white >= 0.18 and yellow >= 0.10 and color_analysis.get("family") in {"白色无色", "黄色"}:
        inferred = "洒金"
        reason = "white-or-yellow-ground-with-gold"

    color_analysis["opencv_pattern_candidate"] = inferred
    color_analysis["opencv_pattern_reason"] = reason

    if not inferred:
        return False
    current = color_analysis.get("pattern") or ""
    primary = str(color_analysis.get("primary") or "")
    detail = str(color_analysis.get("detail") or "")
    has_vlm_color_signal = bool(color_analysis.get("vlm_color_signal"))
    patterned_colors = {"春带彩", "白底青", "飘花", "多彩", "洒金"}
    if has_vlm_color_signal and primary == "多彩":
        return False
    should_apply = False
    if not primary and not detail:
        should_apply = True
    elif current in patterned_colors:
        if current == inferred:
            return False
        should_apply = (
            current == "飘花"
            and inferred == "白底青"
            and white >= 0.20
            and green >= 0.14
            and (cyan + blue) < 0.06
        ) or (current == "多彩" and inferred in {"春带彩", "白底青", "洒金"})
    elif not has_vlm_color_signal and current in {"", "纯色"}:
        should_apply = (
            (inferred == "春带彩" and green >= 0.14 and purple >= 0.08)
            or (inferred == "白底青" and white >= 0.28 and green >= 0.16 and (cyan + blue) < 0.08)
            or (inferred == "洒金" and white >= 0.22 and yellow >= 0.14)
            or (inferred == "多彩" and colored_buckets >= 4)
        )
    if has_vlm_color_signal and current in {"", "纯色"}:
        should_apply = False
    if not should_apply:
        return False
    if current in {"春带彩", "白底青", "飘花"} and current != "纯色":
        if not (current == "飘花" and inferred == "白底青" and white >= 0.20 and green >= 0.14 and (cyan + blue) < 0.06):
            return False
    if current == inferred:
        return False
    color_analysis["pattern"] = inferred
    color_analysis["primary"] = inferred
    if inferred in {"春带彩", "白底青", "飘花", "多彩"}:
        color_analysis["family"] = "多彩"
    elif inferred == "洒金":
        color_analysis["family"] = "黄色"
    return True


def _observed_color_candidates_from_ratios(ratios: dict[str, Any]) -> list[dict[str, Any]]:
    if not ratios:
        return []
    candidates = [
        ("绿色", float(ratios.get("green") or 0)),
        ("蓝绿色", float(ratios.get("cyan") or 0) + float(ratios.get("blue") or 0)),
        ("紫色", float(ratios.get("purple") or 0)),
        ("黄色", float(ratios.get("yellow") or 0)),
        ("红色", float(ratios.get("red_brown") or 0)),
        ("白色无色", float(ratios.get("white") or 0)),
        ("黑色", float(ratios.get("dark") or 0)),
    ]
    result = [
        {"family": family, "ratio": round(ratio, 4)}
        for family, ratio in sorted(candidates, key=lambda item: item[1], reverse=True)
        if ratio >= 0.035
    ]
    return result[:5]


def _normalize_color_family(value: Any) -> str:
    compact = _normalize_text(str(value or "")).replace(" ", "").replace("·", "").replace("/", "")
    catalogs = {
        "绿色": ("绿色", "绿", "翠绿"),
        "蓝绿色": ("蓝绿色", "蓝绿", "青色", "青绿", "蓝水", "晴水", "油青"),
        "白色无色": ("白色无色", "白色", "无色", "白冰", "透明", "清透"),
        "紫色": ("紫色", "紫罗兰", "紫"),
        "黄色": ("黄色", "黄", "黄翡", "冰黄", "金黄", "洒金"),
        "红色": ("红色", "红", "红翡", "红黄"),
        "黑色": ("黑色", "黑", "墨翠", "乌鸡"),
        "多彩": ("多彩", "多色", "彩色", "春带彩", "白底青", "飘花"),
    }
    for canonical, aliases in catalogs.items():
        if compact == canonical or any(alias and alias in compact for alias in aliases):
            return canonical
    return ""


def _normalize_color_pattern(value: Any) -> str:
    compact = _normalize_text(str(value or "")).replace(" ", "").replace("·", "").replace("/", "")
    catalogs = {
        "飘花": ("飘花", "飘蓝花", "飘绿花", "蓝花", "绿花"),
        "白底青": ("白底青", "白底带绿", "白底飘绿"),
        "春带彩": ("春带彩", "春彩"),
        "多彩": ("多彩", "五彩", "多色", "彩色"),
        "洒金": ("洒金", "黄雾", "金点"),
        "纯色": ("纯色", "单色", "满色", "均色", "无花"),
    }
    for canonical, aliases in catalogs.items():
        if compact == canonical or any(alias and alias in compact for alias in aliases):
            return canonical
    return ""


def _color_family_from_color(color: str) -> str:
    mapping = {
        "帝王绿": "绿色",
        "阳绿": "绿色",
        "辣绿": "绿色",
        "苹果绿": "绿色",
        "豆绿": "绿色",
        "绿色": "绿色",
        "蓝水": "蓝绿色",
        "晴水": "蓝绿色",
        "油青": "蓝绿色",
        "白冰": "白色无色",
        "无色": "白色无色",
        "紫罗兰": "紫色",
        "黄翡": "黄色",
        "冰黄": "黄色",
        "洒金": "黄色",
        "红翡": "红色",
        "墨翠": "黑色",
        "飘花": "多彩",
        "白底青": "多彩",
        "春带彩": "多彩",
        "多彩": "多彩",
    }
    return mapping.get(str(color or ""), "")


def _color_pattern_from_color(color: str) -> str:
    if color in {"飘花", "白底青", "春带彩", "多彩", "洒金"}:
        return color
    return "纯色" if color else ""


def _theme_from_text(value: Any) -> str:
    return _first_term(_normalize_text(str(value or "")), JADE_THEMES)


def _extract_size(text: str) -> str:
    patterns = [
        r"(?:单珠约?\s*)?\d+(?:\.\d+)?\s*mm(?:\s*[xX×*]\s*\d+(?:\.\d+)?\s*mm?)?",
        r"(?:高|宽|厚|长|内径|直径)\s*\d+(?:\.\d+)?\s*mm",
        r"\d+(?:\.\d+)?\s*颗",
    ]
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return "; ".join(dict.fromkeys(match.strip() for match in matches if match.strip()))


def _extract_price(text: str) -> float | None:
    value = re.search(r"(?:报价|价格|到手价|卖|¥|￥)?\s*(\d+(?:\.\d+)?)\s*(?:万|w|W)", text)
    if value:
        return float(value.group(1)) * 10000
    value = re.search(r"(?:报价|价格|到手价|卖|¥|￥)\s*(\d{3,8}(?:\.\d+)?)", text)
    if value:
        return float(value.group(1))
    return None


def _repair_mojibake_label(text: str) -> str:
    if not text:
        return ""
    for source_encoding in ("gbk", "latin1"):
        try:
            repaired = text.encode(source_encoding).decode("utf-8")
        except UnicodeError:
            continue
        if _chinese_count(repaired) > _chinese_count(text):
            return repaired
    return text


def _chinese_count(value: str) -> int:
    return sum(1 for char in value if "\u4e00" <= char <= "\u9fff")


def _apply_feedback_learning(analysis: JadeAnalysis, enabled: bool) -> JadeAnalysis:
    if not enabled:
        analysis.signals = {**(analysis.signals or {}), "feedback_learning": {"source": "feedback-learning", "enabled": False, "applied": {}}}
        return analysis
    feedback_signal: dict[str, Any] = {"source": "feedback-learning", "enabled": False, "applied": {}}
    try:
        analysis, feedback_signal = apply_feedback_corrections_to_analysis(analysis)
    except Exception as exc:
        feedback_signal = {"source": "feedback-learning", "enabled": False, "error": str(exc), "applied": {}}
    analysis.signals = {**(analysis.signals or {}), "feedback_learning": feedback_signal}
    return analysis


def _attribute_source(source: str, method: str, value: Any) -> dict[str, Any]:
    return {"source": source, "method": method, "value": value}


def _attribute_sources_for_analysis(analysis: JadeAnalysis, *, source: str, method: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ["color", "water", "style", "theme", "size"]:
        value = getattr(analysis, key, "")
        if value:
            result[key] = _attribute_source(source, method, value)
    if analysis.price is not None:
        result["price"] = _attribute_source(source, method, analysis.price)
    return _apply_feedback_sources(result, analysis.signals.get("feedback_learning", {}))


def _copy_attribute_source(target: dict[str, Any], item: JadeAnalysis, key: str) -> None:
    source = _analysis_attribute_sources(item).get(key)
    if source:
        target[key] = source


def _apply_feedback_sources(attribute_sources: dict[str, Any], feedback_signal: dict[str, Any]) -> dict[str, Any]:
    result = dict(attribute_sources or {})
    for key, change in ((feedback_signal or {}).get("applied") or {}).items():
        result[key] = {**_attribute_source("feedback-learning", "correction-rule", change.get("to", "")), "from": change.get("from", "")}
    return result


def _safe_yolo_detect(image_path: Path) -> tuple[list[YoloDetection], dict[str, Any]]:
    try:
        detections, signal = detect_jade_candidates(image_path)
        return detections, signal
    except Exception as exc:
        return [], {"enabled": False, "error": str(exc)}


def _safe_vlm_analyze(image_path: Path, context_text: str) -> tuple[dict[str, str], dict[str, Any]]:
    try:
        return analyze_jade_image_with_vlm(image_path, context_text=context_text)
    except Exception as exc:
        return {}, {"enabled": False, "error": str(exc)}


def _opencv_analyze(image_path: Path, has_primary_signal: bool) -> dict[str, Any]:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"enabled": False, "error": "opencv-not-installed", "candidates": {}}

    image = cv2.imread(str(image_path))
    if image is None or image.size == 0:
        return {"enabled": False, "error": "image-read-failed", "candidates": {}}

    center_crop = _center_crop(image)
    center_hsv = cv2.cvtColor(center_crop, cv2.COLOR_BGR2HSV)
    crop, subject_roi = _subject_crop(center_crop, center_hsv)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    ratios = _hsv_color_ratios(hsv)
    frame_ratios = _hsv_color_ratios(center_hsv)
    color = _image_color_from_ratios(ratios)
    water, water_features = _image_water_from_features(crop, hsv, ratios)
    style, style_features = _image_style_from_features(crop, ratios)
    candidates = {"color": color}
    if has_primary_signal or color:
        candidates.update({"water": water, "style": style})
    return {
        "enabled": True,
        "candidates": candidates,
        "color_ratios": {key: round(value, 4) for key, value in ratios.items()},
        "frame_color_ratios": {key: round(value, 4) for key, value in frame_ratios.items()},
        "subject_roi": subject_roi,
        "water_features": water_features,
        "style_features": style_features,
    }


def _hsv_color_ratios(hsv: Any) -> dict[str, float]:
    h_chan = hsv[..., 0]
    s_chan = hsv[..., 1]
    v_chan = hsv[..., 2]
    skin_like = (((h_chan <= 25) | (h_chan >= 170)) & (s_chan >= 28) & (s_chan <= 145) & (v_chan >= 70) & (v_chan <= 248))
    valid = (s_chan > 28) & (v_chan > 45) & (v_chan < 248) & ~skin_like
    total = max(1, h_chan.size)
    valid_h = h_chan[valid]
    return {
        "green": float((((valid_h >= 35) & (valid_h <= 85)).sum()) / total),
        "cyan": float((((valid_h >= 86) & (valid_h <= 105)).sum()) / total),
        "blue": float((((valid_h >= 106) & (valid_h <= 125)).sum()) / total),
        "purple": float((((valid_h >= 126) & (valid_h <= 160)).sum()) / total),
        "yellow": float((((valid_h >= 16) & (valid_h <= 34)).sum()) / total),
        "red_brown": float(((((valid_h >= 0) & (valid_h <= 15)) | (valid_h >= 165)).sum()) / total),
        "white": float((((s_chan < 42) & (v_chan > 170)).sum()) / total),
        "dark": float((((v_chan < 72) & (s_chan > 18)).sum()) / total),
    }


def _subject_crop(image: Any, hsv: Any) -> tuple[Any, dict[str, Any]]:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return image, {"source": "center-crop-fallback", "reason": "opencv-not-installed"}

    height, width = image.shape[:2]
    if height < 24 or width < 24:
        return image, {"source": "center-crop-fallback", "reason": "image-too-small"}

    s_chan = hsv[..., 1]
    v_chan = hsv[..., 2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 70, 150)
    edge_mask = cv2.dilate(edges, np.ones((3, 3), dtype=np.uint8), iterations=1) > 0

    skin_like = (((hsv[..., 0] <= 25) | (hsv[..., 0] >= 170)) & (s_chan >= 28) & (s_chan <= 145) & (v_chan >= 70) & (v_chan <= 248))
    colored = (s_chan > 38) & (v_chan > 35) & (v_chan < 248) & ~skin_like
    dark_jade = (v_chan < 95) & (s_chan > 14) & edge_mask
    bright_edge_jade = (s_chan < 65) & (v_chan > 150) & (v_chan < 248) & edge_mask

    yy, xx = np.ogrid[:height, :width]
    center_y = height / 2.0
    center_x = width / 2.0
    ellipse = ((xx - center_x) / max(1.0, width * 0.48)) ** 2 + ((yy - center_y) / max(1.0, height * 0.48)) ** 2 <= 1.0
    mask = (colored | dark_jade | bright_edge_jade) & ellipse

    if int(mask.sum()) < max(32, int(height * width * 0.002)):
        mask = colored | dark_jade | bright_edge_jade
    if int(mask.sum()) < max(32, int(height * width * 0.002)):
        return image, {"source": "center-crop-fallback", "reason": "no-subject-signal"}

    mask_u8 = (mask.astype("uint8")) * 255
    kernel = np.ones((5, 5), dtype=np.uint8)
    mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8), iterations=1)

    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image, {"source": "center-crop-fallback", "reason": "no-contours"}

    image_area = max(1, height * width)
    best: tuple[float, Any, dict[str, Any]] | None = None
    for contour in contours:
        area = float(cv2.contourArea(contour))
        area_ratio = area / image_area
        if area_ratio < 0.0015 or area_ratio > 0.82:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        box_center_x = x + w / 2.0
        box_center_y = y + h / 2.0
        distance = (((box_center_x - center_x) / max(1.0, width / 2.0)) ** 2 + ((box_center_y - center_y) / max(1.0, height / 2.0)) ** 2) ** 0.5
        center_bonus = 0.18 if x <= center_x <= x + w and y <= center_y <= y + h else 0.0
        score = min(area_ratio, 0.35) * 1.6 + max(0.0, 1.0 - distance) * 0.55 + center_bonus
        info = {
            "source": "subject-contour",
            "x": int(x),
            "y": int(y),
            "w": int(w),
            "h": int(h),
            "area_ratio": round(area_ratio, 4),
            "center_distance": round(float(distance), 4),
            "score": round(float(score), 4),
        }
        if best is None or score > best[0]:
            best = (score, contour, info)

    if best is None:
        return image, {"source": "center-crop-fallback", "reason": "no-valid-subject-contour"}

    _, contour, info = best
    x, y, w, h = cv2.boundingRect(contour)
    pad = max(8, int(max(w, h) * 0.14))
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(width, x + w + pad)
    y1 = min(height, y + h + pad)
    if x1 <= x0 or y1 <= y0:
        return image, {"source": "center-crop-fallback", "reason": "invalid-subject-box"}
    info = {
        **info,
        "expanded_x": int(x0),
        "expanded_y": int(y0),
        "expanded_w": int(x1 - x0),
        "expanded_h": int(y1 - y0),
        "expanded_area_ratio": round(float((x1 - x0) * (y1 - y0) / image_area), 4),
    }
    return image[y0:y1, x0:x1], info


def _center_crop(image: Any) -> Any:
    h, w = image.shape[:2]
    side_h = max(40, int(h * 0.78))
    side_w = max(40, int(w * 0.78))
    cy, cx = h // 2, w // 2
    return image[max(0, cy - side_h // 2) : min(h, cy + side_h // 2), max(0, cx - side_w // 2) : min(w, cx + side_w // 2)]


def _best_yolo_detection(detections: list[YoloDetection]) -> YoloDetection | None:
    for detection in detections or []:
        if getattr(detection, "style", "") or getattr(detection, "theme", ""):
            return detection
    return detections[0] if detections else None


def _image_color_from_ratios(ratios: dict[str, float]) -> str:
    colored = sum(ratios.get(key, 0.0) for key in ["green", "cyan", "blue", "purple", "yellow", "red_brown"])
    dominant = max(ratios.get(key, 0.0) for key in ["green", "cyan", "blue", "purple", "yellow", "red_brown"])
    if colored >= 0.18 and dominant <= colored * 0.60 and ratios.get("white", 0.0) < 0.45:
        return "飘花"
    if ratios.get("dark", 0.0) > 0.32 and colored < 0.16:
        return "墨翠"
    if ratios.get("red_brown", 0.0) > 0.08 and ratios.get("red_brown", 0.0) >= ratios.get("yellow", 0.0):
        return "红翡"
    if ratios.get("yellow", 0.0) + ratios.get("red_brown", 0.0) > 0.12:
        return "黄翡"
    if ratios.get("purple", 0.0) > 0.08:
        return "紫罗兰"
    if ratios.get("green", 0.0) > 0.10 and ratios.get("green", 0.0) >= ratios.get("cyan", 0.0):
        return "阳绿"
    if ratios.get("cyan", 0.0) > 0.08 and ratios.get("blue", 0.0) > 0.03:
        return "蓝水"
    if ratios.get("cyan", 0.0) > 0.08:
        return "晴水"
    if ratios.get("blue", 0.0) > 0.06:
        return "蓝水"
    if ratios.get("white", 0.0) > 0.18:
        return "白冰"
    return ""


def _image_water_from_features(image: Any, hsv: Any, ratios: dict[str, float]) -> tuple[str, dict[str, float]]:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return "", {}
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(hsv[..., 2]))
    saturation = float(np.mean(hsv[..., 1]))
    contrast = float(np.std(gray))
    edge_density = float((cv2.Canny(gray, 80, 160) > 0).sum() / max(1, gray.size))
    texture = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    jade_ratio = sum(ratios.get(key, 0.0) for key in ["green", "cyan", "blue", "purple", "yellow", "red_brown"]) + min(ratios.get("white", 0.0), 0.35)
    clarity = max(0.0, min(1.0, (brightness - 80) / 150))
    clarity -= min(0.35, edge_density * 3.5)
    clarity -= min(0.30, texture / 900.0)
    clarity += min(0.12, jade_ratio * 0.20)
    clarity = max(0.0, min(1.0, clarity))
    features = {
        "brightness": round(brightness, 3),
        "saturation": round(saturation, 3),
        "contrast": round(contrast, 3),
        "edge_density": round(edge_density, 5),
        "texture": round(texture, 3),
        "jade_color_ratio": round(jade_ratio, 3),
        "clarity_score": round(clarity, 3),
    }
    if jade_ratio < 0.08:
        return "", features
    if clarity >= 0.88 and brightness >= 185 and texture < 35:
        return "高冰", features
    if clarity >= 0.78 and brightness >= 170 and texture < 90:
        return "高冰", features
    if clarity >= 0.66 and brightness >= 150 and texture < 120:
        return "冰种", features
    if clarity >= 0.50 and brightness >= 125:
        return "糯冰", features
    if clarity >= 0.32:
        return "糯种", features
    return "豆种", features


def _image_style_from_features(image: Any, ratios: dict[str, float]) -> tuple[str, dict[str, Any]]:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return "", {}
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 70, 150)
    edge_density = float((edges > 0).sum() / max(1, edges.size))
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contour = _largest_contour_features(contours, hierarchy, gray.shape)
    circle_count = _count_hough_circles(gray)
    jade_ratio = sum(ratios.get(key, 0.0) for key in ["green", "cyan", "blue", "purple", "yellow", "red_brown"]) + min(ratios.get("white", 0.0), 0.35)
    features = {"jade_color_ratio": round(jade_ratio, 3), "edge_density": round(edge_density, 5), "circle_count": circle_count, **contour}
    if jade_ratio < 0.08 and edge_density < 0.015:
        return "", features
    area = float(contour.get("area_ratio", 0.0))
    circularity = float(contour.get("circularity", 0.0))
    aspect = float(contour.get("aspect_ratio", 0.0))
    hole = float(contour.get("hole_ratio", 0.0))
    solidity = float(contour.get("solidity", 0.0))
    if circle_count >= 5 and area < 0.65:
        return "珠串", features
    if hole >= 0.32 and area >= 0.16 and circularity >= 0.28:
        return "手镯", features
    if 0.08 <= hole < 0.32 and 0.70 <= aspect <= 1.35 and circularity >= 0.22:
        return "平安扣", features
    if hole < 0.08 and 0.08 <= area <= 0.55 and circularity >= 0.42 and 0.55 <= aspect <= 1.80:
        return "蛋面", features
    if area >= 0.10 and (aspect > 1.65 or aspect < 0.58 or solidity < 0.58):
        return "吊坠", features
    return "", features


def _largest_contour_features(contours: Any, hierarchy: Any, shape: tuple[int, int]) -> dict[str, float]:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {}
    image_area = max(1, shape[0] * shape[1])
    if not contours:
        return {"area_ratio": 0.0, "circularity": 0.0, "aspect_ratio": 0.0, "hole_ratio": 0.0, "solidity": 0.0}
    areas = [float(cv2.contourArea(contour)) for contour in contours]
    index = int(np.argmax(areas))
    largest = contours[index]
    area = max(0.0, areas[index])
    perimeter = float(cv2.arcLength(largest, True))
    x, y, w, h = cv2.boundingRect(largest)
    hull = cv2.convexHull(largest)
    hull_area = float(cv2.contourArea(hull))
    hole_area = 0.0
    if hierarchy is not None and len(hierarchy) > 0:
        for child_index, item in enumerate(hierarchy[0]):
            if int(item[3]) == index:
                hole_area += max(0.0, float(cv2.contourArea(contours[child_index])))
    return {
        "area_ratio": round(area / image_area, 4),
        "circularity": round(0.0 if perimeter <= 0 else 4 * np.pi * area / (perimeter * perimeter), 4),
        "aspect_ratio": round(w / max(1, h), 4),
        "hole_ratio": round(hole_area / max(1.0, area), 4),
        "solidity": round(0.0 if hull_area <= 0 else area / hull_area, 4),
    }


def _count_hough_circles(gray: Any) -> int:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return 0
    h, w = gray.shape[:2]
    min_radius = max(5, int(min(h, w) * 0.025))
    max_radius = max(min_radius + 2, int(min(h, w) * 0.12))
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=max(10, min_radius * 2), param1=90, param2=18, minRadius=min_radius, maxRadius=max_radius)
    if circles is None:
        return 0
    return int(len(np.round(circles[0, :]).astype("int")))


def _prefer_incoming(key: str, incoming: str, current: str, incoming_scores: dict[str, float], existing_scores: dict[str, float]) -> bool:
    if not incoming:
        return False
    if not current:
        return True
    return incoming_scores.get(key, 0.0) > existing_scores.get(key, 0.0)


def _analysis_attribute_sources(analysis: JadeAnalysis) -> dict[str, Any]:
    sources = (analysis.signals or {}).get("attribute_sources") or {}
    return sources if isinstance(sources, dict) else {}


def _analysis_fusion_scores(analysis: JadeAnalysis) -> dict[str, float]:
    scores = (analysis.signals or {}).get("attribute_fusion_scores") or {}
    if not isinstance(scores, dict):
        return {}
    result: dict[str, float] = {}
    for key, value in scores.items():
        try:
            result[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return result


def _fusion_scores_for_sources(analysis: JadeAnalysis, sources: dict[str, Any]) -> dict[str, float]:
    return {key: round(_attribute_source_score(value, analysis, key), 3) for key, value in (sources or {}).items()}


def _attribute_source_score(source: Any, item: JadeAnalysis, key: str) -> float:
    if not isinstance(source, dict):
        if key in {"style", "theme"} and item.detections:
            return 0.86
        if item.evidence_image_paths and key in {"color", "water", "style", "theme"}:
            return 0.60
        return float(item.confidence or 0.0)
    source_name = str(source.get("source") or "")
    method = str(source.get("method") or "")
    base = {
        "feedback-learning": 0.96,
        "yolo": 0.88,
        "local-vlm": 0.78,
        "speech": 0.74,
        "text": 0.72,
        "live-context": 0.70,
        "image-context": 0.66,
        "opencv": 0.46,
    }.get(source_name, 0.50)
    if source_name == "opencv" and method == "shape-heuristic":
        base -= 0.08
    if source_name == "opencv" and key in {"color", "water"}:
        base -= 0.04
    return base + min(0.08, max(0.0, float(item.confidence or 0.0)) * 0.08)


def _merge_unique(existing: list[str], incoming: list[str], limit: int) -> list[str]:
    result = list(existing or [])
    for item in incoming or []:
        if item and item not in result:
            result.append(item)
    return result[:limit]


def _analysis_match_key(analysis: JadeAnalysis) -> tuple[str, str, str, str]:
    return analysis.color, analysis.water, analysis.style, analysis.theme


def _find_matching_live_product(match_key: tuple[str, str, str, str]) -> Any | None:
    from app.state import app_state
    color, water, style, theme = match_key
    for product in app_state.products.values():
        matched = 0
        for key, value in [("color", color), ("water", water), ("style", style), ("theme", theme)]:
            existing = getattr(product, key, "")
            if value and existing and value != existing:
                matched = -10
                break
            if value and existing == value:
                matched += 1
        if matched >= 2:
            return product
    return None


def _find_current_session_product(session: Any | None, analysis: JadeAnalysis) -> Any | None:
    if session is None or not getattr(session, "current_product_id", ""):
        return None
    from app.state import app_state
    product = app_state.products.get(session.current_product_id)
    if product is None:
        return None
    conflicts = 0
    for key in CORE_ATTRIBUTES:
        incoming = getattr(analysis, key, "")
        existing = getattr(product, key, "")
        if incoming and existing and incoming != existing:
            conflicts += 1
    return None if conflicts >= 2 else product


def _has_live_product_update_signal(analysis: JadeAnalysis) -> bool:
    return bool(analysis.color or analysis.water or analysis.style or analysis.theme or analysis.size or analysis.price is not None or analysis.evidence_texts or analysis.detections)


def _prefer(current: str, incoming: str) -> str:
    return current or incoming


def _selling_points(analysis: JadeAnalysis) -> list[str]:
    points: list[str] = []
    if analysis.color:
        points.append(f"颜色：{analysis.color}")
    if analysis.water:
        points.append(f"种水：{analysis.water}")
    if analysis.style:
        points.append(f"样式：{analysis.style}")
    if analysis.theme:
        points.append(f"题材：{analysis.theme}")
    return points


def _confidence(analysis: JadeAnalysis) -> float:
    score = 0.0
    for value in [analysis.color, analysis.water, analysis.style, analysis.theme, analysis.size]:
        if value:
            score += 0.16
    if analysis.price is not None:
        score += 0.08
    if analysis.evidence_texts:
        score += 0.12
    if analysis.evidence_image_paths:
        score += 0.10
    if analysis.detections:
        score += 0.16
    if (analysis.signals or {}).get("feedback_learning", {}).get("applied"):
        score += 0.06
    return round(min(score, 1.0), 3)
