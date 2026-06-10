from datetime import datetime, timezone
import json
from pathlib import Path

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile

from app.auth_utils import require_role
from app.repositories import delete_product as delete_product_record
from app.repositories import save_product
from app.schemas import Product, ProductCreate
from app.services.jade_annotation_service import (
    WORKSPACE_DIR,
    approve_jade_annotation_whole_image_box,
    build_jade_annotation_export,
    confirm_jade_annotation_whole_image_box,
    get_jade_annotation_tasks,
    import_jade_annotation_zip,
    review_jade_annotation_task,
    save_jade_annotation_boxes,
)
from app.services.jade_batch_feedback_summary_service import MINIMUM_YOLO_READY_RECORDS, summarize_jade_batch_feedback
from app.services.jade_batch_trace_service import feedback_record_matches_batch
from app.services.jade_evaluation_service import evaluate_jade_feedback_samples
from app.services.jade_feedback_learning_service import clean_attribute_value, get_feedback_learning_status
from app.services.jade_frame_ocr_service import get_jade_ocr_runtime_status
from app.services.jade_multimodal_service import JadeAnalysis, analyze_jade_image, analyze_jade_text, merge_jade_analysis
from app.services.jade_review_flags_service import jade_analysis_review_flags
from app.services.jade_training_job_service import get_jade_yolo_training_run_status, start_jade_yolo_training
from app.services.jade_training_service import (
    auto_prepare_validation_split,
    build_jade_feedback_dataset,
    class_names_from_feedback,
    get_jade_training_status,
    read_feedback_records,
)
from app.services.jade_vlm_service import analyze_jade_image_with_vlm, get_vlm_runtime_status
from app.services.jade_yolo_service import get_yolo_runtime_status
from app.state import app_state

router = APIRouter()
PRODUCT_STATUS_ON_SALE = "在售"
WORKSPACE_DIR = Path(__file__).resolve().parents[3]
JADE_SAMPLE_UPLOAD_DIR = WORKSPACE_DIR / "uploads" / "jade-samples"
JADE_FEEDBACK_PATH = WORKSPACE_DIR / "data" / "jade_feedback.jsonl"
JADE_UPLOAD_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
JADE_UPLOAD_MAX_BYTES = 15 * 1024 * 1024
JADE_BATCH_MAX_ITEMS = 50


def _as_on_sale(product: Product) -> Product:
    if product.status == PRODUCT_STATUS_ON_SALE:
        return product
    updated = product.model_copy(update={"status": PRODUCT_STATUS_ON_SALE})
    app_state.products[updated.id] = updated
    save_product(updated)
    return updated


def _build_jade_feedback_dataset_with_auto_val(*, split: str = "train", val_every: int = 5, write_yaml: bool = True) -> dict:
    result = build_jade_feedback_dataset(split=split, val_every=val_every, write_yaml=write_yaml)
    result["auto_fix"] = auto_prepare_validation_split()
    return result


def _dict_payload(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _string_list_payload(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _float_payload(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _jade_upload_suffix(filename: str, *, default: str = ".jpg") -> str:
    suffix = Path(filename or "").suffix.lower() or default
    if suffix not in JADE_UPLOAD_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(JADE_UPLOAD_IMAGE_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"仅支持图片格式：{allowed}")
    return suffix


async def _read_jade_upload_bytes(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > JADE_UPLOAD_MAX_BYTES:
        max_mb = JADE_UPLOAD_MAX_BYTES // (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"单张图片不能超过 {max_mb}MB")
    if not _looks_like_supported_image(content):
        raise HTTPException(status_code=400, detail="上传内容不是可识别的图片文件")
    return content


def _looks_like_supported_image(content: bytes) -> bool:
    if content.startswith(b"\xff\xd8\xff"):
        return True
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if content.startswith(b"BM"):
        return True
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return True
    return False


def _normalized_feedback_evidence(value: object) -> dict:
    evidence = _dict_payload(value)
    return {
        **evidence,
        "images": _string_list_payload(evidence.get("images")),
        "texts": _string_list_payload(evidence.get("texts")),
        "detections": evidence.get("detections") if isinstance(evidence.get("detections"), list) else [],
    }


@router.get("/jade-taxonomy/options")
async def get_jade_taxonomy_options() -> dict:
    return {
        "status": "ok",
        "colors": ["阳绿", "蓝水", "晴水", "紫罗兰", "白冰", "飘花", "黄翡", "墨翠", "红翡"],
        "waters": ["玻璃种", "高冰", "冰种", "冰糯", "糯冰", "细糯", "糯种", "豆种"],
        "styles": ["手镯", "珠串", "蛋面", "吊坠", "戒指", "牌子", "平安扣", "摆件"],
        "themes": ["观音", "佛公", "如意", "叶子", "山水", "貔貅", "葫芦", "无事牌", "财神", "龙牌", "福瓜", "福豆"],
    }


@router.get("", response_model=list[Product])
async def list_products(status: str | None = None) -> list[Product]:
    return [_as_on_sale(product) for product in app_state.products.values()]


@router.get("/jade-model/status")
async def get_jade_model_status() -> dict:
    yolo = get_yolo_runtime_status()
    ocr = get_jade_ocr_runtime_status()
    vlm = get_vlm_runtime_status()
    feedback_learning = get_feedback_learning_status()
    training = get_jade_training_status()
    readiness = {
        "can_analyze_image": True,
        "can_read_frame_text": bool(ocr.get("enabled")),
        "has_jade_yolo_model": yolo.get("model_kind") == "jade-trained",
        "uses_pretrained_yolo_fallback": bool(yolo.get("pretrained_fallback")),
        "has_vlm": bool(vlm.get("enabled")),
        "has_feedback_learning": bool(feedback_learning.get("enabled")),
        "has_yolo_training_data": int((training.get("feedback") or {}).get("usable_for_yolo") or 0) > 0,
        "requires_manual_box": int((training.get("feedback") or {}).get("requires_manual_box") or 0),
    }
    return {
        "status": "ok",
        "readiness": readiness,
        "yolo": yolo,
        "ocr": ocr,
        "vlm": vlm,
        "feedback_learning": feedback_learning,
        "training": training,
        "limits": {
            "upload_image_extensions": sorted(JADE_UPLOAD_IMAGE_EXTENSIONS),
            "upload_max_bytes": JADE_UPLOAD_MAX_BYTES,
            "upload_max_mb": JADE_UPLOAD_MAX_BYTES // (1024 * 1024),
            "batch_max_items": JADE_BATCH_MAX_ITEMS,
            "page_default_batch_items": 20,
            "batch_readiness_min_yolo_ready_records": MINIMUM_YOLO_READY_RECORDS,
        },
        "fusion": {
            "image": [
                "yolo-detection-primary",
                "opencv-color",
                "opencv-water",
                "opencv-style",
            ],
            "speech": ["stt-transcript-primary", "transcript-keyword-attributes"],
            "weak_supplement": ["frame-ocr-weak", "local-vlm-prelabel-weak", "feedback-learning-correction"],
            "attributes": ["color", "water", "style", "theme", "size", "price"],
            "policy": "YOLO + STT are primary; OCR and VLM are weak supplements and cannot create live products by themselves.",
        },
    }


@router.post("/jade-model/vlm-probe")
async def probe_jade_vlm(file: UploadFile | None = File(default=None), text: str = Form(default="")) -> dict:
    status = get_vlm_runtime_status()
    cleaned = (text or "").strip()
    if file is None:
        return {
            "status": "no-image",
            "message": "请上传一张翡翠图片后再探测 VLM",
            "runtime": status,
            "attributes": {},
            "raw_text": "",
        }

    original_filename = file.filename or "vlm-probe.jpg"
    suffix = _jade_upload_suffix(original_filename)
    JADE_SAMPLE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = JADE_SAMPLE_UPLOAD_DIR / f"{app_state.new_id('jade-vlm-probe')}{suffix}"
    stored_path.write_bytes(await _read_jade_upload_bytes(file))
    attributes, runtime = analyze_jade_image_with_vlm(stored_path, context_text=cleaned)
    return {
        "status": "ok" if attributes else "no-attributes",
        "image": f"/uploads/jade-samples/{stored_path.name}",
        "runtime": runtime,
        "attributes": attributes,
        "raw_text": str(runtime.get("raw_text") or ""),
    }


@router.post("/jade-model/vlm-prelabel")
async def save_jade_vlm_prelabel(file: UploadFile | None = File(default=None), text: str = Form(default="")) -> dict:
    cleaned = (text or "").strip()
    if file is None:
        raise HTTPException(status_code=400, detail="请上传一张翡翠图片")

    original_filename = file.filename or "vlm-prelabel.jpg"
    suffix = _jade_upload_suffix(original_filename)
    JADE_SAMPLE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = JADE_SAMPLE_UPLOAD_DIR / f"{app_state.new_id('jade-vlm-prelabel')}{suffix}"
    stored_path.write_bytes(await _read_jade_upload_bytes(file))
    image_url = f"/uploads/jade-samples/{stored_path.name}"
    attributes, runtime = analyze_jade_image_with_vlm(stored_path, context_text=cleaned)
    if not attributes:
        return {
            "status": "no-attributes",
            "image": image_url,
            "runtime": runtime,
            "attributes": {},
            "message": "VLM 未返回可用属性，未写入训练池",
        }

    corrected = {
        key: clean_attribute_value(key, attributes.get(key))
        for key in ["color", "water", "style", "theme"]
    }
    record = {
        "id": app_state.new_id("jade-vlm-prelabel"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "image": image_url,
            "text": cleaned,
            "source_filename": original_filename,
        },
        "predicted": corrected,
        "corrected": corrected,
        "evidence": {
            "images": [image_url],
            "texts": [cleaned] if cleaned else [],
            "detections": [],
        },
        "confidence": 0.45,
        "source": "vlm-prelabel",
        "attribute_sources": {
            key: {
                "source": "local-vlm",
                "method": "image-language-prelabel",
                "value": value,
            }
            for key, value in corrected.items()
            if value
        },
        "needs_review": True,
        "review_status": "pending",
        "review_reason": "vlm-prelabel-needs-human-confirmation",
        "runtime": runtime,
    }
    suggested_classes = class_names_from_feedback(record)
    record["training"] = {
        "suggested_classes": suggested_classes,
        "yolo_ready": bool(suggested_classes),
        "requires_manual_box": len(suggested_classes) != 1 if suggested_classes else False,
    }
    JADE_FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with JADE_FEEDBACK_PATH.open("a", encoding="utf-8") as feedback_file:
        feedback_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {
        "status": "ok",
        "id": record["id"],
        "image": image_url,
        "runtime": runtime,
        "attributes": corrected,
        "needs_review": True,
        "training": record["training"],
    }


@router.post("/jade-analysis/sample")
async def analyze_jade_sample(file: UploadFile | None = File(default=None), text: str = Form(default="")) -> dict:
    cleaned = (text or "").strip()
    if file is None and not cleaned:
        raise HTTPException(status_code=400, detail="请上传图片或填写主播讲解文本")

    analyses: list[JadeAnalysis] = []
    image_url = ""
    original_filename = ""
    if file is not None:
        original_filename = file.filename or "sample.jpg"
        suffix = _jade_upload_suffix(original_filename)
        JADE_SAMPLE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        stored_path = JADE_SAMPLE_UPLOAD_DIR / f"{app_state.new_id('jade-sample')}{suffix}"
        stored_path.write_bytes(await _read_jade_upload_bytes(file))
        image_url = f"/uploads/jade-samples/{stored_path.name}"
        image_analysis = analyze_jade_image(stored_path, context_text=cleaned)
        image_analysis.evidence_image_paths = [image_url]
        analyses.append(image_analysis)

    if cleaned:
        analyses.append(analyze_jade_text(cleaned))

    if not analyses:
        raise HTTPException(status_code=400, detail="没有可分析的内容")

    result = merge_jade_analysis(*analyses) if len(analyses) > 1 else analyses[0]
    payload = _analysis_to_payload(result)
    payload["input"] = {"image": image_url or original_filename, "text": cleaned}
    payload["runtime"] = {
        "yolo": get_yolo_runtime_status(),
        "ocr": get_jade_ocr_runtime_status(),
        "vlm": get_vlm_runtime_status(),
        "feedback_learning": get_feedback_learning_status(),
        "training": get_jade_training_status(),
    }
    return payload


@router.post("/jade-analysis/batch")
async def analyze_jade_batch(
    files: list[UploadFile] | None = File(default=None),
    text: str = Form(default=""),
    max_items: int = Form(default=20),
) -> dict:
    cleaned = (text or "").strip()
    uploads = files or []
    if not uploads and not cleaned:
        raise HTTPException(status_code=400, detail="请上传至少一张图片或填写主播讲解文本")
    if max_items <= 0:
        raise HTTPException(status_code=400, detail="max_items 必须大于 0")
    if max_items > JADE_BATCH_MAX_ITEMS:
        raise HTTPException(status_code=400, detail=f"max_items 不能超过 {JADE_BATCH_MAX_ITEMS}")
    if len(uploads) > max_items:
        raise HTTPException(status_code=400, detail=f"一次最多分析 {max_items} 张图片")

    batch_id = app_state.new_id("jade-analysis-batch")
    items: list[dict] = []
    shared_text_analysis = analyze_jade_text(cleaned) if cleaned else None
    if uploads:
        JADE_SAMPLE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        for index, file in enumerate(uploads, start=1):
            original_filename = file.filename or f"sample-{index}.jpg"
            suffix = _jade_upload_suffix(original_filename)
            stored_path = JADE_SAMPLE_UPLOAD_DIR / f"{app_state.new_id('jade-batch-sample')}{suffix}"
            stored_path.write_bytes(await _read_jade_upload_bytes(file))
            image_url = f"/uploads/jade-samples/{stored_path.name}"

            analyses: list[JadeAnalysis] = []
            image_analysis = analyze_jade_image(stored_path, context_text=cleaned)
            image_analysis.evidence_image_paths = [image_url]
            analyses.append(image_analysis)
            if shared_text_analysis is not None:
                analyses.append(shared_text_analysis)

            result = merge_jade_analysis(*analyses) if len(analyses) > 1 else analyses[0]
            item = _analysis_to_payload(result)
            item["input"] = {
                "image": image_url,
                "source_filename": original_filename,
                "text": cleaned,
                "batch_id": batch_id,
            }
            items.append(item)
    else:
        if shared_text_analysis is None:
            raise HTTPException(status_code=400, detail="没有可分析的文本")
        item = _analysis_to_payload(shared_text_analysis)
        item["input"] = {"image": "", "source_filename": "", "text": cleaned, "batch_id": batch_id}
        items.append(item)

    return {
        "status": "ok",
        "batch_id": batch_id,
        "count": len(items),
        "items": items,
        "review_summary": _review_flag_counts(items),
        "runtime": {
            "yolo": get_yolo_runtime_status(),
            "ocr": get_jade_ocr_runtime_status(),
            "vlm": get_vlm_runtime_status(),
            "feedback_learning": get_feedback_learning_status(),
            "training": get_jade_training_status(),
        },
    }


@router.post("/jade-analysis/feedback")
async def save_jade_analysis_feedback(payload: dict = Body(...)) -> dict:
    raw_corrected = _dict_payload(payload.get("corrected"))
    corrected = {
        key: clean_attribute_value(key, raw_corrected.get(key))
        for key in ["color", "water", "style", "theme"]
    }
    if not any(str(corrected.get(key, "")).strip() for key in ["color", "water", "style", "theme"]):
        raise HTTPException(status_code=400, detail="请至少填写一个人工校正字段")

    record = {
        "id": app_state.new_id("jade-feedback"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": _dict_payload(payload.get("input")),
        "predicted": _dict_payload(payload.get("predicted")),
        "corrected": corrected,
        "evidence": _normalized_feedback_evidence(payload.get("evidence")),
        "confidence": _float_payload(payload.get("confidence")),
        "source": "sample-analysis",
        "attribute_sources": _dict_payload(payload.get("attribute_sources")),
        "needs_review": False,
        "review_status": "approved",
    }
    suggested_classes = class_names_from_feedback(record)
    has_image = bool((record["evidence"].get("images") or []) or record["input"].get("image"))
    whole_image_ready = len(suggested_classes) == 1 and has_image
    record["training"] = {
        "suggested_classes": suggested_classes,
        "yolo_ready": bool(suggested_classes),
        "requires_manual_box": bool(suggested_classes) and not whole_image_ready,
        "box_mode": "whole-image" if whole_image_ready else "",
        "box_confirmed_by": "human" if whole_image_ready else "",
    }
    JADE_FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with JADE_FEEDBACK_PATH.open("a", encoding="utf-8") as feedback_file:
        feedback_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    dataset = _build_jade_feedback_dataset_with_auto_val(split="train", val_every=5, write_yaml=True) if whole_image_ready else None
    return {
        "status": "ok",
        "id": record["id"],
        "path": str(JADE_FEEDBACK_PATH),
        "training": record["training"],
        "dataset": dataset,
    }


@router.post("/jade-analysis/feedback/batch")
async def save_jade_analysis_feedback_batch(payload: dict = Body(...)) -> dict:
    raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    if not raw_items:
        raise HTTPException(status_code=400, detail="items 不能为空")

    records: list[dict] = []
    results: list[dict] = []
    has_whole_image_ready = False
    seen_keys: set[str] = set()
    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            results.append({"index": index, "status": "skipped", "reason": "item must be an object"})
            continue
        raw_corrected = _dict_payload(item.get("corrected"))
        corrected = {
            key: clean_attribute_value(key, raw_corrected.get(key))
            for key in ["color", "water", "style", "theme"]
        }
        if not any(str(corrected.get(key, "")).strip() for key in ["color", "water", "style", "theme"]):
            results.append({"index": index, "status": "skipped", "reason": "missing corrected attributes"})
            continue
        input_payload = _dict_payload(item.get("input"))
        evidence_payload = _normalized_feedback_evidence(item.get("evidence"))
        image_key = str(input_payload.get("image") or "|".join(evidence_payload.get("images") or [])).strip()
        dedupe_key = json.dumps(
            {
                "image": image_key,
                "text": str(input_payload.get("text") or "").strip(),
                "corrected": corrected,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        if dedupe_key in seen_keys:
            results.append({"index": index, "status": "skipped", "reason": "duplicate in batch"})
            continue
        seen_keys.add(dedupe_key)

        record = {
            "id": app_state.new_id("jade-feedback"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input": input_payload,
            "predicted": _dict_payload(item.get("predicted")),
            "corrected": corrected,
            "evidence": evidence_payload,
            "confidence": _float_payload(item.get("confidence")),
            "source": "batch-sample-analysis",
            "attribute_sources": _dict_payload(item.get("attribute_sources")),
            "needs_review": False,
            "review_status": "approved",
        }
        suggested_classes = class_names_from_feedback(record)
        has_image = bool((evidence_payload.get("images") or []) or input_payload.get("image"))
        whole_image_ready = len(suggested_classes) == 1 and has_image
        has_whole_image_ready = has_whole_image_ready or whole_image_ready
        record["training"] = {
            "suggested_classes": suggested_classes,
            "yolo_ready": bool(suggested_classes),
            "requires_manual_box": bool(suggested_classes) and not whole_image_ready,
            "box_mode": "whole-image" if whole_image_ready else "",
            "box_confirmed_by": "human" if whole_image_ready else "",
        }
        records.append(record)
        results.append({
            "index": index,
            "status": "ok",
            "id": record["id"],
            "training": record["training"],
        })

    if not records:
        raise HTTPException(status_code=400, detail="没有可保存的校正反馈")

    JADE_FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with JADE_FEEDBACK_PATH.open("a", encoding="utf-8") as feedback_file:
        for record in records:
            feedback_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    dataset = _build_jade_feedback_dataset_with_auto_val(split="train", val_every=5, write_yaml=True) if has_whole_image_ready else None
    skipped_reasons: dict[str, int] = {}
    for result in results:
        if result.get("status") == "skipped":
            reason = str(result.get("reason") or "unknown")
            skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1
    return {
        "status": "ok",
        "saved": len(records),
        "skipped": len(raw_items) - len(records),
        "skipped_reasons": skipped_reasons,
        "path": str(JADE_FEEDBACK_PATH),
        "results": results,
        "dataset": dataset,
    }


@router.get("/jade-analysis/batches/{batch_id}/feedback")
async def get_jade_analysis_batch_feedback(batch_id: str) -> dict:
    cleaned = (batch_id or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="batch_id 不能为空")
    records = read_feedback_records(JADE_FEEDBACK_PATH)
    matched = [record for record in records if feedback_record_matches_batch(record, cleaned)]
    return {
        "status": "ok",
        "batch_id": cleaned,
        "feedback_path": str(JADE_FEEDBACK_PATH),
        "count": len(matched),
        "summary": summarize_jade_batch_feedback(matched),
        "records": [_feedback_record_summary(record) for record in matched],
    }



@router.get("/jade-training/status")
async def get_jade_training_readiness() -> dict:
    return get_jade_training_status()


@router.post("/jade-training/build-dataset")
async def build_jade_training_dataset(payload: dict = Body(default_factory=dict)) -> dict:
    split = str(payload.get("split") or "train")
    val_every = int(payload.get("val_every", 5))
    write_yaml = bool(payload.get("write_yaml", True))
    try:
        return _build_jade_feedback_dataset_with_auto_val(split=split, val_every=val_every, write_yaml=write_yaml)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jade-training/train/status")
async def get_jade_training_run_status() -> dict:
    return get_jade_yolo_training_run_status()


@router.post("/jade-training/train/start")
async def start_jade_training(payload: dict = Body(default_factory=dict)) -> dict:
    try:
        return start_jade_yolo_training(
            epochs=int(payload.get("epochs", 50)),
            imgsz=int(payload.get("imgsz", 640)),
            batch=str(payload.get("batch", "auto")),
            model=str(payload.get("model", "yolo11n.pt")),
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jade-evaluation/run")
async def run_jade_evaluation(payload: dict = Body(default_factory=dict)) -> dict:
    limit = int(payload.get("limit", 30))
    return evaluate_jade_feedback_samples(limit=limit)


@router.get("/jade-annotation/tasks")
async def list_jade_annotation_tasks(limit: int = 80) -> dict:
    return get_jade_annotation_tasks(limit=limit)


@router.post("/jade-annotation/export")
async def export_jade_annotation_tasks(payload: dict = Body(default_factory=dict)) -> dict:
    limit = int(payload.get("limit", 80))
    return build_jade_annotation_export(limit=limit)


@router.post("/jade-annotation/tasks/{feedback_id}/review")
async def review_jade_annotation_feedback_task(feedback_id: str, payload: dict = Body(...)) -> dict:
    action = str(payload.get("action") or "")
    corrected = payload.get("corrected") if isinstance(payload.get("corrected"), dict) else None
    try:
        return review_jade_annotation_task(feedback_id, action, corrected=corrected)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/jade-annotation/tasks/{feedback_id}/whole-image-box")
async def confirm_jade_annotation_feedback_whole_image_box(feedback_id: str) -> dict:
    try:
        return confirm_jade_annotation_whole_image_box(feedback_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/jade-annotation/tasks/{feedback_id}/approve-whole-image-box")
async def approve_jade_annotation_feedback_whole_image_box(feedback_id: str, payload: dict = Body(default_factory=dict)) -> dict:
    corrected = payload.get("corrected") if isinstance(payload.get("corrected"), dict) else None
    auto_build_dataset = bool(payload.get("auto_build_dataset", True))
    try:
        result = approve_jade_annotation_whole_image_box(feedback_id, corrected=corrected)
        if auto_build_dataset:
            result["dataset"] = _build_jade_feedback_dataset_with_auto_val(split="train", val_every=5, write_yaml=True)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/jade-annotation/tasks/{feedback_id}/boxes")
async def save_jade_annotation_feedback_boxes(feedback_id: str, payload: dict = Body(...)) -> dict:
    boxes = payload.get("boxes") if isinstance(payload.get("boxes"), list) else []
    try:
        return save_jade_annotation_boxes(feedback_id, boxes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/jade-annotation/import")
async def import_jade_annotation_package(
    file: UploadFile = File(...),
    split: str = Form(default="auto"),
    auto_val_ratio: float = Form(default=0.2),
) -> dict:
    suffix = Path(file.filename or "labels.zip").suffix.lower()
    if suffix != ".zip":
        raise HTTPException(status_code=400, detail="请上传 zip 标注包")
    upload_dir = WORKSPACE_DIR / "uploads" / "jade-annotation-import"
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / f"{app_state.new_id('jade-annotation')}.zip"
    stored_path.write_bytes(await file.read())
    try:
        return import_jade_annotation_zip(stored_path, split=split, auto_val_ratio=auto_val_ratio)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{product_id}/jade-annotation")
async def annotate_product_jade_attributes(product_id: str, payload: dict = Body(...)) -> dict:
    product = app_state.products.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    raw_corrected = payload.get("corrected") if isinstance(payload.get("corrected"), dict) else payload
    corrected = {
        key: clean_attribute_value(key, raw_corrected.get(key))
        for key in ["color", "water", "style", "theme"]
    }
    if not any(corrected.values()):
        raise HTTPException(status_code=400, detail="请至少标注颜色、种水、样式、题材中的一个字段")

    predicted = {
        "color": product.color,
        "water": product.water,
        "style": product.style,
        "theme": product.theme,
    }
    merged_attributes = {
        key: corrected.get(key) or predicted.get(key, "")
        for key in ["color", "water", "style", "theme"]
    }
    attribute_sources = dict(product.attribute_sources or {})
    fusion_scores = dict(product.fusion_scores or {})
    for key, value in corrected.items():
        if not value:
            continue
        attribute_sources[key] = {
            "source": "live-product-manual-annotation",
            "method": "human-label",
            "value": value,
            "from": predicted.get(key, ""),
        }
        fusion_scores[key] = 98.0

    updated = product.model_copy(
        update={
            "name": " ".join(
                part for part in [
                    merged_attributes["color"],
                    merged_attributes["water"],
                    merged_attributes["style"] or merged_attributes["theme"],
                ]
                if part
            ) or product.name,
            "category": merged_attributes["style"] or merged_attributes["theme"] or product.category,
            "status": PRODUCT_STATUS_ON_SALE,
            "color": merged_attributes["color"],
            "water": merged_attributes["water"],
            "style": merged_attributes["style"],
            "theme": merged_attributes["theme"],
            "attribute_sources": attribute_sources,
            "fusion_scores": fusion_scores,
        }
    )
    app_state.products[updated.id] = updated
    save_product(updated)

    now = datetime.now(timezone.utc)
    record = {
        "id": app_state.new_id("jade-product-annotation"),
        "created_at": now.isoformat(),
        "input": {
            "image": updated.evidence_image_paths[0] if updated.evidence_image_paths else "",
            "text": "\n".join(updated.evidence_texts[-8:]),
            "product_id": updated.id,
            "product_name": updated.name,
        },
        "predicted": predicted,
        "corrected": merged_attributes,
        "evidence": {
            "images": updated.evidence_image_paths,
            "texts": updated.evidence_texts,
        },
        "confidence": updated.analysis_confidence,
        "source": "live-product-manual-annotation",
        "attribute_sources": attribute_sources,
        "needs_review": False,
        "review_status": "approved",
    }
    suggested_classes = class_names_from_feedback(record)
    has_image = bool(updated.evidence_image_paths)
    whole_image_ready = len(suggested_classes) == 1 and has_image
    record["training"] = {
        "suggested_classes": suggested_classes,
        "yolo_ready": bool(suggested_classes),
        "requires_manual_box": bool(suggested_classes) and not whole_image_ready,
        "box_mode": "whole-image" if whole_image_ready else "",
        "box_confirmed_by": "human" if whole_image_ready else "",
    }
    JADE_FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with JADE_FEEDBACK_PATH.open("a", encoding="utf-8") as feedback_file:
        feedback_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    dataset = _build_jade_feedback_dataset_with_auto_val(split="train", val_every=5, write_yaml=True) if whole_image_ready else None
    return {
        "status": "ok",
        "product": updated.model_dump(mode="json"),
        "feedback_id": record["id"],
        "training": record["training"],
        "dataset": dataset,
    }


@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: str) -> Product:
    product = app_state.products.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return _as_on_sale(product)


@router.post("", response_model=Product)
async def create_product(payload: ProductCreate) -> Product:
    data = payload.model_dump()
    data["status"] = PRODUCT_STATUS_ON_SALE
    product = Product(id=app_state.new_id("prod"), **data)
    app_state.products[product.id] = product
    save_product(product)
    return product


@router.put("/{product_id}", response_model=Product)
async def update_product(product_id: str, payload: ProductCreate) -> Product:
    if product_id not in app_state.products:
        raise HTTPException(status_code=404, detail="商品不存在")
    data = payload.model_dump()
    data["status"] = PRODUCT_STATUS_ON_SALE
    product = Product(id=product_id, **data)
    app_state.products[product_id] = product
    save_product(product)
    return product


@router.post("/{product_id}/set-idle", response_model=Product)
async def set_product_idle(product_id: str) -> Product:
    product = app_state.products.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return _as_on_sale(product)


@router.post("/{product_id}/set-active", response_model=Product)
async def set_product_active(product_id: str) -> Product:
    product = app_state.products.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return _as_on_sale(product)


@router.delete("/{product_id}", dependencies=[require_role("管理员")])
async def delete_product(product_id: str) -> dict[str, str]:
    if product_id not in app_state.products:
        raise HTTPException(status_code=404, detail="商品不存在")
    app_state.products.pop(product_id)
    delete_product_record(product_id)
    return {"status": "deleted", "deleted_at": datetime.now(timezone.utc).isoformat()}


def _analysis_to_payload(analysis: JadeAnalysis) -> dict:
    return {
        "name": analysis.full_name(),
        "attributes": {
            "color": analysis.color,
            "water": analysis.water,
            "style": analysis.style,
            "theme": analysis.theme,
            "size": analysis.size,
            "price": analysis.price,
        },
        "confidence": analysis.confidence,
        "evidence": {
            "images": analysis.evidence_image_paths,
            "texts": analysis.evidence_texts,
            "detections": analysis.detections,
        },
        "signals": analysis.signals,
        "review_flags": jade_analysis_review_flags(analysis),
    }


def _review_flag_counts(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        flags = item.get("review_flags") if isinstance(item, dict) else []
        if not isinstance(flags, list):
            continue
        for flag in flags:
            key = str(flag or "").strip()
            if key:
                counts[key] = counts.get(key, 0) + 1
    return counts


def _feedback_record_summary(record: dict) -> dict:
    input_payload = _dict_payload(record.get("input"))
    evidence = _normalized_feedback_evidence(record.get("evidence"))
    return {
        "id": record.get("id", ""),
        "created_at": record.get("created_at", ""),
        "source": record.get("source", ""),
        "input": input_payload,
        "corrected": _dict_payload(record.get("corrected")),
        "predicted": _dict_payload(record.get("predicted")),
        "confidence": _float_payload(record.get("confidence")),
        "training": _dict_payload(record.get("training")),
        "evidence": {
            "images": evidence.get("images") or [],
            "texts": evidence.get("texts") or [],
        },
    }
