from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.services.jade_multimodal_service import (
    JADE_COLORS,
    JADE_STYLES,
    JADE_THEMES,
    JADE_WATERS,
    analyze_jade_text,
)


def _flatten_terms(value: Any) -> set[str]:
    terms: set[str] = set()
    if value is None:
        return terms
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            terms.add(normalized)
        return terms
    if isinstance(value, Mapping):
        for key, nested in value.items():
            terms.update(_flatten_terms(key))
            terms.update(_flatten_terms(nested))
        return terms
    if isinstance(value, Iterable):
        for nested in value:
            terms.update(_flatten_terms(nested))
    return terms


def _assert_contains(catalog: Any, required_terms: set[str]) -> None:
    terms = _flatten_terms(catalog)
    missing = required_terms - terms
    assert not missing, f"missing jade taxonomy terms: {sorted(missing)}"


def test_jade_taxonomy_covers_core_attributes():
    _assert_contains(JADE_COLORS, {"阳绿", "帝王绿", "蓝水", "紫罗兰", "红翡", "白冰"})
    _assert_contains(JADE_WATERS, {"玻璃种", "冰种", "高冰", "糯种", "豆种"})
    _assert_contains(JADE_STYLES, {"手镯", "珠串", "珠链", "蛋面", "吊坠", "戒指", "耳饰", "摆件"})
    _assert_contains(JADE_THEMES, {"观音", "佛公", "平安扣", "如意", "叶子", "山水", "貔貅", "龙牌", "财神", "福瓜", "福豆"})


def test_text_recognition_extracts_color_water_style_theme_contract():
    result = analyze_jade_text("阳绿冰种观音吊坠，18k金镶嵌，适合直播间快速建档。")

    assert getattr(result, "color", None) == "阳绿"
    assert getattr(result, "water", None) == "冰种"
    assert getattr(result, "style", None) == "吊坠"
    assert getattr(result, "theme", None) == "观音"
