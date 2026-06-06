from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from app.services.jade_multimodal_service import JadeAnalysis, analyze_jade_image, analyze_jade_text, merge_jade_analysis
from app.services.jade_training_service import (
    DEFAULT_FEEDBACK_PATH,
    is_feedback_record_training_eligible,
    read_feedback_records,
    resolve_feedback_image,
)


ATTRIBUTES = ["color", "water", "style", "theme"]
ATTRIBUTE_LABELS = {
    "color": "颜色",
    "water": "种水",
    "style": "样式",
    "theme": "题材",
}


def evaluate_jade_feedback_samples(
    *,
    feedback_path: Path = DEFAULT_FEEDBACK_PATH,
    limit: int = 30,
) -> dict[str, Any]:
    records = read_feedback_records(feedback_path)
    eligible_records = [record for record in records if is_feedback_record_training_eligible(record)]
    selected = [record for record in eligible_records if has_corrected_attribute(record)][-max(1, min(200, limit)) :]
    metrics = {key: {"correct": 0, "total": 0, "accuracy": 0.0} for key in ATTRIBUTES}
    details: list[dict[str, Any]] = []
    hard_cases: list[dict[str, Any]] = []
    evaluated = 0
    skipped = 0
    modality_counts: Counter[str] = Counter()
    misses: dict[str, Counter[tuple[str, str]]] = {key: Counter() for key in ATTRIBUTES}
    source_metrics: dict[str, dict[str, dict[str, int]]] = {key: {} for key in ATTRIBUTES}

    for record in selected:
        analysis = analyze_feedback_record(record)
        corrected = normalize_corrected(record.get("corrected") or {})
        if analysis is None:
            skipped += 1
            details.append(
                {
                    "id": record.get("id", ""),
                    "status": "skipped",
                    "reason": "no-image-or-text",
                    "corrected": corrected,
                    "predicted": {},
                }
            )
            continue

        evaluated += 1
        modality_counts[evidence_mode(record)] += 1
        predicted = analysis_to_attributes(analysis)
        matches: dict[str, bool] = {}
        for key in ATTRIBUTES:
            expected = corrected.get(key, "")
            if not expected:
                continue
            actual = predicted.get(key, "")
            matched = attribute_matches(actual, expected)
            source_name = attribute_source_name(analysis, key)
            source_bucket = source_metrics[key].setdefault(source_name, {"correct": 0, "total": 0})
            source_bucket["total"] += 1
            source_bucket["correct"] += 1 if matched else 0
            metrics[key]["total"] += 1
            metrics[key]["correct"] += 1 if matched else 0
            matches[key] = matched
            if not matched:
                misses[key][(actual or "未识别", expected)] += 1
                hard_cases.append(build_hard_case(record, key, actual, expected, analysis))
        details.append(
            {
                "id": record.get("id", ""),
                "status": "evaluated",
                "corrected": corrected,
                "predicted": predicted,
                "matches": matches,
                "confidence": analysis.confidence,
                "evidence_mode": evidence_mode(record),
                "attribute_sources": (analysis.signals or {}).get("attribute_sources") or {},
            }
        )

    for item in metrics.values():
        total = item["total"]
        item["accuracy"] = round(item["correct"] / total, 3) if total else 0.0

    total_correct = sum(item["correct"] for item in metrics.values())
    total_count = sum(item["total"] for item in metrics.values())
    return {
        "status": "ok",
        "feedback_path": str(feedback_path),
        "records": len(records),
        "eligible_records": len(eligible_records),
        "selected": len(selected),
        "evaluated": evaluated,
        "skipped": skipped,
        "overall": {
            "correct": total_correct,
            "total": total_count,
            "accuracy": round(total_correct / total_count, 3) if total_count else 0.0,
        },
        "metrics": metrics,
        "modality_counts": dict(modality_counts),
        "source_metrics": finalize_source_metrics(source_metrics),
        "weakest_attribute": weakest_attribute(metrics),
        "misses": {
            key: [
                {"pair": f"{actual} -> {expected}", "count": count}
                for (actual, expected), count in counter.most_common(5)
            ]
            for key, counter in misses.items()
        },
        "hard_cases": hard_cases[-20:],
        "recommendations": build_recommendations(metrics, misses),
        "details": details[-20:],
    }


def has_corrected_attribute(record: dict[str, Any]) -> bool:
    corrected = record.get("corrected") or {}
    return any(clean_value(corrected.get(key)) for key in ATTRIBUTES)


def analyze_feedback_record(record: dict[str, Any]) -> JadeAnalysis | None:
    analyses: list[JadeAnalysis] = []
    image_path = resolve_feedback_image(record)
    text = str((record.get("input") or {}).get("text") or "").strip()
    if image_path is not None and image_path.exists():
        analyses.append(analyze_jade_image(image_path, context_text=text, use_feedback_learning=False))
    if text:
        analyses.append(analyze_jade_text(text, use_feedback_learning=False))
    if not analyses:
        return None
    return merge_jade_analysis(*analyses, use_feedback_learning=False) if len(analyses) > 1 else analyses[0]


def evidence_mode(record: dict[str, Any]) -> str:
    image_path = resolve_feedback_image(record)
    has_image = bool(image_path is not None and image_path.exists())
    has_text = bool(str((record.get("input") or {}).get("text") or "").strip())
    if has_image and has_text:
        return "image+text"
    if has_image:
        return "image-only"
    if has_text:
        return "text-only"
    return "none"


def attribute_source_name(analysis: JadeAnalysis, key: str) -> str:
    sources = (analysis.signals or {}).get("attribute_sources") or {}
    if not isinstance(sources, dict):
        return "unknown"
    source = sources.get(key)
    if not isinstance(source, dict):
        return "unknown"
    source_name = str(source.get("source") or "unknown")
    method = str(source.get("method") or "")
    return f"{source_name}/{method}" if method else source_name


def finalize_source_metrics(source_metrics: dict[str, dict[str, dict[str, int]]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for key, buckets in source_metrics.items():
        rows: list[dict[str, Any]] = []
        for source, counts in buckets.items():
            total = counts["total"]
            correct = counts["correct"]
            rows.append(
                {
                    "source": source,
                    "correct": correct,
                    "total": total,
                    "accuracy": round(correct / total, 3) if total else 0.0,
                }
            )
        rows.sort(key=lambda item: (-int(item["total"]), -float(item["accuracy"]), str(item["source"])))
        result[key] = rows
    return result


def normalize_corrected(corrected: dict[str, Any]) -> dict[str, str]:
    return {key: clean_value(corrected.get(key)) for key in ATTRIBUTES}


def analysis_to_attributes(analysis: JadeAnalysis) -> dict[str, str]:
    return {
        "color": clean_value(analysis.color),
        "water": clean_value(analysis.water),
        "style": clean_value(analysis.style),
        "theme": clean_value(analysis.theme),
    }


def build_hard_case(record: dict[str, Any], key: str, actual: str, expected: str, analysis: JadeAnalysis) -> dict[str, Any]:
    image_path = resolve_feedback_image(record)
    source = str(record.get("source") or "")
    return {
        "id": str(record.get("id") or ""),
        "attribute": key,
        "attribute_label": ATTRIBUTE_LABELS.get(key, key),
        "predicted": actual or "未识别",
        "corrected": expected,
        "confidence": analysis.confidence,
        "source": source,
        "image": public_image_path(image_path),
    }


def public_image_path(path: Path | None) -> str:
    if path is None:
        return ""
    parts = path.parts
    if "uploads" in parts:
        index = parts.index("uploads")
        return "/" + "/".join(parts[index:])
    return str(path)


def attribute_matches(actual: str, expected: str) -> bool:
    left = compact(actual)
    right = compact(expected)
    if not left or not right:
        return False
    return left == right or left in right or right in left


def clean_value(value: Any) -> str:
    return str(value or "").strip()


def compact(value: str) -> str:
    return clean_value(value).replace(" ", "").replace("·", "").replace("/", "")


def weakest_attribute(metrics: dict[str, dict[str, Any]]) -> str:
    candidates = [
        (key, value["accuracy"], value["total"])
        for key, value in metrics.items()
        if value["total"] > 0
    ]
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (item[1], -item[2]))
    return candidates[0][0]


def build_recommendations(metrics: dict[str, dict[str, Any]], misses: dict[str, Counter[tuple[str, str]]]) -> list[str]:
    result: list[str] = []
    weakest = weakest_attribute(metrics)
    if weakest:
        metric = metrics[weakest]
        label = ATTRIBUTE_LABELS[weakest]
        result.append(
            f"优先优化{label}：当前命中 {metric['correct']}/{metric['total']}，准确率 {round(metric['accuracy'] * 100)}%。"
        )
    for key in ATTRIBUTES:
        label = ATTRIBUTE_LABELS[key]
        if metrics[key]["total"] == 0:
            result.append(f"{label}缺少人工校正样本，无法评估；后续请多提交这个字段的校正。")
            continue
        if metrics[key]["accuracy"] < 0.7:
            common = misses[key].most_common(1)
            if common:
                (actual, expected), count = common[0]
                result.append(f"{label}常见错配：{actual} -> {expected}，出现 {count} 次。")
            else:
                result.append(f"{label}准确率偏低，需要补充更多样本校正。")
    if not result:
        result.append("当前样本下四个字段没有明显薄弱项；继续增加真实直播样本评估稳定性。")
    return result[:6]
