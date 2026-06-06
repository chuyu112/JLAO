from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.services.jade_training_service import is_feedback_record_training_eligible


WORKSPACE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_FEEDBACK_PATH = WORKSPACE_DIR / "data" / "jade_feedback.jsonl"
ATTRIBUTES = ["color", "water", "style", "theme"]
MIN_CORRECTION_COUNT = 2
STANDARD_ATTRIBUTE_ALIASES: dict[str, dict[str, str]] = {
    "color": {
        "帝王绿": "帝王绿",
        "阳绿": "阳绿",
        "辣绿": "辣绿",
        "苹果绿": "苹果绿",
        "豆绿": "豆绿",
        "绿色": "绿色",
        "蓝水": "蓝水",
        "晴水": "晴水",
        "油青": "油青",
        "紫罗兰": "紫罗兰",
        "春带彩": "春带彩",
        "白冰": "白冰",
        "无色": "无色",
        "白底青": "白底青",
        "飘花": "飘花",
        "黄翡": "黄翡",
        "冰黄": "冰黄",
        "洒金": "洒金",
        "墨翠": "墨翠",
        "红翡": "红翡",
        "多彩": "多彩",
        "金点": "洒金",
        "洒金翡": "洒金",
        "白底飘绿": "白底青",
        "白底带绿": "白底青",
        "正阳绿": "阳绿",
        "高阳绿": "帝王绿",
        "满绿": "帝王绿",
        "果绿": "苹果绿",
        "苹果绿色": "苹果绿",
        "油青绿": "油青",
        "灰绿": "油青",
        "灰绿色": "油青",
        "冰种黄翡": "冰黄",
        "高冰黄翡": "冰黄",
    },
    "water": {
        "玻璃种": "玻璃种",
        "高冰": "高冰",
        "冰种": "冰种",
        "冰胶": "冰胶",
        "起冰": "起冰",
        "冰糯": "冰糯",
        "糯冰": "糯冰",
        "起胶": "起胶",
        "糯化": "糯化",
        "细糯": "细糯",
        "糯种": "糯种",
        "豆种": "豆种",
        "冰起胶": "冰胶",
        "冰胶感": "冰胶",
        "起冰感": "起冰",
        "胶感": "起胶",
        "胶块感": "起胶",
        "果冻感": "起胶",
        "玛瑙感": "起胶",
        "糯化种": "糯化",
        "化开": "糯化",
        "棉化开": "糯化",
        "细糯种": "细糯",
        "糯冰种": "糯冰",
    },
    "style": {
        "手镯": "手镯",
        "珠串": "珠串",
        "蛋面": "蛋面",
        "戒面": "戒面",
        "戒指": "戒指",
        "挂件": "挂件",
        "吊坠": "吊坠",
        "平安扣": "平安扣",
        "摆件": "摆件",
        "把件": "把件",
        "耳饰": "耳饰",
        "牌子": "挂件",
        "牌坠": "挂件",
        "小挂件": "挂件",
        "龙牌": "挂件",
        "山水牌": "挂件",
        "无事牌": "挂件",
        "观音": "挂件",
        "佛公": "挂件",
        "叶子": "挂件",
        "如意": "挂件",
        "葫芦": "挂件",
        "福瓜": "挂件",
        "貔貅": "挂件",
        "镶嵌坠": "吊坠",
        "裸石坠": "吊坠",
    },
    "theme": {
        "观音": "观音",
        "佛公": "佛公",
        "如意": "如意",
        "叶子": "叶子",
        "山水": "山水",
        "貔貅": "貔貅",
        "葫芦": "葫芦",
        "无事牌": "无事牌",
        "财神": "财神",
        "龙": "龙",
        "福瓜": "福瓜",
        "龙牌": "龙",
        "龙纹": "龙",
        "生肖龙": "龙",
        "山水牌": "山水",
        "平安无事牌": "无事牌",
        "福豆": "福瓜",
        "瓜": "福瓜",
    },
}
ATTRIBUTE_ALIASES: dict[str, dict[str, str]] = {
    "color": {
        "阳绿": "阳绿",
        "辣绿": "阳绿",
        "正阳绿": "阳绿",
        "高阳绿": "阳绿",
        "满绿": "阳绿",
        "帝王绿": "阳绿",
        "果绿": "阳绿",
        "苹果绿": "阳绿",
        "秧苗绿": "阳绿",
        "蓝水": "蓝水",
        "老蓝水": "蓝水",
        "蓝底": "蓝水",
        "蓝绿": "蓝水",
        "蓝绿色": "蓝水",
        "海蓝": "蓝水",
        "天空蓝": "蓝水",
        "晴水": "晴水",
        "晴底": "晴水",
        "晴蓝": "晴水",
        "晴绿": "晴水",
        "晴水底": "晴水",
        "紫罗兰": "紫罗兰",
        "紫色": "紫罗兰",
        "淡紫": "紫罗兰",
        "春彩": "紫罗兰",
        "紫春": "紫罗兰",
        "茄紫": "紫罗兰",
        "白冰": "白冰",
        "冰白": "白冰",
        "白底": "白冰",
        "无色": "白冰",
        "玻璃白": "白冰",
        "高冰白": "白冰",
        "飘花": "飘花",
        "飘蓝花": "飘花",
        "飘绿花": "飘花",
        "蓝花": "飘花",
        "绿花": "飘花",
        "飘色": "飘花",
        "黄翡": "黄翡",
        "黄雾": "黄翡",
        "洒金": "黄翡",
        "鸡油黄": "黄翡",
        "黄加绿": "黄翡",
        "墨翠": "墨翠",
        "黑冰": "墨翠",
        "乌鸡": "墨翠",
        "黑色": "墨翠",
        "红翡": "红翡",
        "红雾": "红翡",
        "红黄翡": "红翡",
    },
    "water": {
        "玻璃种": "玻璃种",
        "玻璃底": "玻璃种",
        "高冰": "高冰",
        "高冰种": "高冰",
        "高冰底": "高冰",
        "冰种": "冰种",
        "冰底": "冰种",
        "冰糯": "冰糯",
        "冰糯种": "冰糯",
        "糯冰": "糯冰",
        "糯冰种": "糯冰",
        "细糯": "细糯",
        "细糯种": "细糯",
        "糯种": "糯种",
        "糯底": "糯种",
        "豆种": "豆种",
        "豆底": "豆种",
    },
    "style": {
        "手镯": "手镯",
        "镯子": "手镯",
        "圆条": "手镯",
        "正圈": "手镯",
        "贵妃镯": "手镯",
        "平安镯": "手镯",
        "珠串": "珠串",
        "手串": "珠串",
        "珠子": "珠串",
        "珠链": "珠串",
        "项链": "珠串",
        "蛋面": "蛋面",
        "戒面": "蛋面",
        "鸽子蛋": "蛋面",
        "吊坠": "吊坠",
        "挂件": "吊坠",
        "坠子": "吊坠",
        "戒指": "戒指",
        "戒托": "戒指",
        "牌子": "牌子",
        "无事牌": "牌子",
        "平安扣": "平安扣",
        "扣子": "平安扣",
        "怀古": "平安扣",
        "摆件": "摆件",
        "把件": "摆件",
        "手把件": "摆件",
    },
    "theme": {
        "观音": "观音",
        "观世音": "观音",
        "佛公": "佛公",
        "弥勒佛": "佛公",
        "笑佛": "佛公",
        "如意": "如意",
        "如意头": "如意",
        "叶子": "叶子",
        "树叶": "叶子",
        "金枝玉叶": "叶子",
        "山水": "山水",
        "山水牌": "山水",
        "貔貅": "貔貅",
        "皮丘": "貔貅",
        "葫芦": "葫芦",
        "福禄": "葫芦",
        "无事牌": "无事牌",
        "平安无事牌": "无事牌",
        "财神": "财神",
        "关公": "财神",
        "武财神": "财神",
        "龙牌": "龙牌",
        "龙纹": "龙牌",
        "生肖龙": "龙牌",
    },
}

_cache_mtime: float | None = None
_cache_rules: dict[str, dict[str, str]] = {}
_cache_stats: dict[str, Any] = {}


def get_feedback_learning_status(feedback_path: Path = DEFAULT_FEEDBACK_PATH) -> dict[str, Any]:
    rules, stats = get_feedback_correction_rules(feedback_path)
    return {
        "source": "feedback-learning",
        "enabled": bool(any(rules[key] for key in ATTRIBUTES)),
        "min_correction_count": MIN_CORRECTION_COUNT,
        "feedback_path": str(feedback_path),
        "rules": rules,
        "stats": stats,
    }


def apply_feedback_corrections_to_analysis(analysis: Any) -> tuple[Any, dict[str, Any]]:
    values = {key: str(getattr(analysis, key, "") or "").strip() for key in ATTRIBUTES}
    corrected, signal = apply_feedback_corrections(values)
    for key, value in corrected.items():
        setattr(analysis, key, value)
    return analysis, signal


def apply_feedback_corrections(values: dict[str, str]) -> tuple[dict[str, str], dict[str, Any]]:
    rules, stats = get_feedback_correction_rules()
    corrected = {key: clean_attribute_value(key, values.get(key)) for key in ATTRIBUTES}
    applied: dict[str, dict[str, str]] = {}
    for key in ATTRIBUTES:
        current = clean_attribute_value(key, corrected.get(key))
        if not current:
            continue
        target = rules.get(key, {}).get(current, "")
        if target and target != current:
            corrected[key] = target
            applied[key] = {"from": current, "to": target}
    return corrected, {
        "source": "feedback-learning",
        "applied": applied,
        "rule_counts": {key: len(rules.get(key, {})) for key in ATTRIBUTES},
        "records": stats.get("records", 0),
    }


def get_feedback_correction_rules(
    feedback_path: Path = DEFAULT_FEEDBACK_PATH,
) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    global _cache_mtime, _cache_rules, _cache_stats
    mtime = feedback_path.stat().st_mtime if feedback_path.exists() else 0.0
    if _cache_mtime == mtime:
        return _cache_rules, _cache_stats

    pair_counts: dict[str, Counter[tuple[str, str]]] = {key: Counter() for key in ATTRIBUTES}
    records = 0
    eligible_records = 0
    skipped_unreviewed_or_rejected = 0
    if feedback_path.exists():
        for line in feedback_path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            records += 1
            if not is_feedback_record_training_eligible(record):
                skipped_unreviewed_or_rejected += 1
                continue
            eligible_records += 1
            predicted = record.get("predicted") or {}
            corrected = record.get("corrected") or {}
            for key in ATTRIBUTES:
                before = clean_attribute_value(key, predicted.get(key))
                after = clean_attribute_value(key, corrected.get(key))
                if before and after and before != after:
                    pair_counts[key][(before, after)] += 1

    rules: dict[str, dict[str, str]] = {key: {} for key in ATTRIBUTES}
    conflicts: dict[str, list[dict[str, Any]]] = {key: [] for key in ATTRIBUTES}
    for key in ATTRIBUTES:
        by_before: dict[str, Counter[str]] = {}
        for (before, after), count in pair_counts[key].items():
            by_before.setdefault(before, Counter())[after] += count
        for before, counter in by_before.items():
            after, count = counter.most_common(1)[0]
            if count >= MIN_CORRECTION_COUNT:
                rules[key][before] = after
            if len(counter) > 1:
                conflicts[key].append(
                    {
                        "from": before,
                        "candidates": [
                            {"to": candidate, "count": candidate_count}
                            for candidate, candidate_count in counter.most_common(5)
                        ],
                    }
                )

    _cache_mtime = mtime
    _cache_rules = rules
    _cache_stats = {
        "records": records,
        "eligible_records": eligible_records,
        "skipped_unreviewed_or_rejected": skipped_unreviewed_or_rejected,
        "pair_counts": {
            key: [
                {"from": before, "to": after, "count": count}
                for (before, after), count in counter.most_common(10)
            ]
            for key, counter in pair_counts.items()
        },
        "conflicts": conflicts,
    }
    return _cache_rules, _cache_stats


def clean_value(value: Any) -> str:
    return str(value or "").strip()


def clean_attribute_value(key: str, value: Any) -> str:
    text = repair_mojibake(clean_value(value))
    if not text:
        return ""
    standard = standard_attribute_alias(key, text)
    if standard:
        return standard
    aliases = ATTRIBUTE_ALIASES.get(key, {})
    compact = text.replace(" ", "").replace("·", "").replace("/", "")
    if compact in aliases:
        return aliases[compact]
    for alias, canonical in aliases.items():
        if alias and alias in compact:
            return canonical
    return text


def standard_attribute_alias(key: str, value: str) -> str:
    compact = value.replace(" ", "").replace("·", "").replace("/", "")
    aliases = STANDARD_ATTRIBUTE_ALIASES.get(key, {})
    if compact in aliases:
        return aliases[compact]
    for alias, canonical in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if alias and alias in compact:
            return canonical
    return ""


def repair_mojibake(value: str) -> str:
    text = clean_value(value)
    if not text:
        return ""
    try:
        repaired = text.encode("gbk").decode("utf-8")
    except UnicodeError:
        return text
    return repaired if any("\u4e00" <= char <= "\u9fff" for char in repaired) else text
