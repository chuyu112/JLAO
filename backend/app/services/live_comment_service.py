import asyncio
import hashlib
import io
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.schemas import VirtualCustomerEvent
from app.state import app_state
from app.ws.manager import manager


logger = logging.getLogger(__name__)

ALIYUN_OCR_AK_ID = os.getenv("ALIYUN_AK_ID") or os.getenv("ALIYUN_ACCESS_KEY_ID", "")
ALIYUN_OCR_AK_SECRET = os.getenv("ALIYUN_AK_SECRET") or os.getenv("ALIYUN_ACCESS_KEY_SECRET", "")
ALIYUN_OCR_REGION = os.getenv("ALIYUN_OCR_REGION", "cn-hangzhou")
ALIYUN_OCR_ENDPOINT = os.getenv("ALIYUN_OCR_ENDPOINT", "ocr-api.cn-hangzhou.aliyuncs.com")
COMMENT_OCR_INTERVAL_SECONDS = float(os.getenv("JLAO_COMMENT_OCR_INTERVAL_SECONDS", "1.0"))
MAX_LIVE_COMMENTS_PER_SESSION = 200
MAX_SEEN_SIGNATURES_PER_SESSION = 600
MAX_PENDING_COMMENT_EVENTS_PER_SESSION = 200

_session_ocr_locks: dict[str, asyncio.Lock] = {}
_session_last_ocr_at: dict[str, float] = {}
_seen_comment_signatures: dict[str, set[str]] = {}
_seen_comment_order: dict[str, list[str]] = {}
_seen_comment_texts: dict[str, list[str]] = {}
_pending_comment_events: dict[str, list[VirtualCustomerEvent]] = {}
_warned_not_configured = False

_BADGE_PATTERN = re.compile(r"^(?:粉丝|新粉|铁粉|灯牌|观众|粉丝团|管理员)\s*")
_COMMENT_SPLIT_PATTERN = re.compile(r"^(.{1,20}?)[：:]\s*(.{2,})$")
_BADGED_LINE_PATTERN = re.compile(r"^(?:粉丝|新粉|铁粉|灯牌|观众|粉丝团|管理员)\s+([^\s：:]{1,16})\s+(.{2,})$")
_MASKED_NICKNAME_PATTERN = re.compile(r"^([A-Za-z0-9_\u4e00-\u9fff.-]{1,14}\*{1,3})\s+(.{2,})$")
_SENSITIVE_QUERY_PATTERN = re.compile(r"\b(AccessKeyId|Signature|SignatureNonce)=([^&\s)]+)")
_WINDOWS_OCR_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Path = $env:JLAO_OCR_IMAGE
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStreamWithContentType, Windows.Storage.Streams, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime] | Out-Null
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and
    $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]
function Await($operation, [Type]$resultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($resultType)
    $task = $asTask.Invoke($null, @($operation))
    $task.Wait()
    $task.Result
}
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$language = [Windows.Globalization.Language]::new('zh-Hans-CN')
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
if ($null -eq $engine) {
    throw 'Windows OCR zh-Hans-CN recognizer is unavailable'
}
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$result.Lines | ForEach-Object {
    if ($_.Text) {
        $_.Text
    }
}
"""
_IGNORE_MARKERS = (
    "江苏健康广播",
    "FM100",
    "AM846",
    "官方补贴",
    "明天12",
    "玉器之乡",
    "主播",
    "关注",
    "聊一聊",
    "七天无理由",
    "七天",
    "保真",
    "精品",
    "珠宝鉴定",
    "翡翠特色",
    "专场",
    "中国工艺",
    "国家高级",
    "非物质文化遗产",
    "点赞",
    "分享",
    "粉丝团",
)


class AliyunOcrNotConfigured(RuntimeError):
    pass


class WindowsOcrUnavailable(RuntimeError):
    pass


async def process_live_comments_from_frame(session_id: str, image_path: Path) -> list[VirtualCustomerEvent]:
    if not _should_scan_now(session_id):
        return []

    lock = _lock_for_session(session_id)
    if lock.locked():
        return []

    async with lock:
        if not _should_scan_now(session_id):
            return []
        _session_last_ocr_at[session_id] = time.monotonic()
        _update_ocr_status(session_id, running=True, last_error="", last_image=str(image_path))

        try:
            lines = await recognize_comment_lines(image_path)
        except AliyunOcrNotConfigured as exc:
            _warn_ocr_not_configured(str(exc))
            _update_ocr_status(session_id, running=False, last_error=str(exc), last_line_count=0, last_event_count=0)
            return []
        except Exception as exc:
            error = sanitize_ocr_error(str(exc))
            logger.warning("live comment OCR failed for %s: %s", session_id, error)
            _update_ocr_status(session_id, running=False, last_error=error, last_line_count=0, last_event_count=0)
            return []

        events = dedupe_live_comment_events(session_id, events_from_ocr_lines(session_id, lines))
        _update_ocr_status(
            session_id,
            running=False,
            last_error="",
            last_line_count=len(lines),
            last_event_count=len(events),
            last_lines=lines[:12],
        )
        if not events:
            return []

        comments = app_state.live_comments.setdefault(session_id, [])
        for event in events:
            existing_index = next((index for index, item in enumerate(comments) if item.id == event.id), -1)
            if existing_index >= 0:
                comments[existing_index] = event
            else:
                comments.insert(0, event)
            await manager.broadcast(session_id, "live_comment_event", event.model_dump(mode="json"))
        del comments[MAX_LIVE_COMMENTS_PER_SESSION:]
        return events


async def recognize_comment_lines(image_path: Path) -> list[str]:
    image_variants = await asyncio.to_thread(_read_comment_region_variants, image_path)
    windows_lines: list[str] = []
    windows_unavailable = False
    for image_bytes in image_variants:
        try:
            windows_lines.extend(await asyncio.to_thread(_recognize_with_windows_ocr, image_bytes))
        except WindowsOcrUnavailable:
            windows_unavailable = True
            break
        except Exception as exc:
            logger.debug("Windows OCR variant failed: %s", sanitize_ocr_error(str(exc)))

    if not windows_unavailable:
        return _unique_clean_lines(windows_lines)

    payload = await asyncio.to_thread(_recognize_general_with_aliyun, image_variants[0])
    return extract_ocr_lines(payload)


def events_from_ocr_lines(
    session_id: str,
    lines: Iterable[str],
    now: datetime | None = None,
) -> list[VirtualCustomerEvent]:
    created_at = now or datetime.now(timezone.utc)
    events: list[VirtualCustomerEvent] = []

    for candidate_line in _candidate_comment_lines(lines):
        parsed = _parse_comment_line(candidate_line)
        if not parsed:
            continue

        nickname, content, event_type = parsed
        event_key = f"{session_id}|{nickname}|{content}|{created_at.isoformat()}|{len(events)}"
        event_id = f"lcomm-{hashlib.sha1(event_key.encode('utf-8')).hexdigest()[:12]}"
        customer_id = f"live-{hashlib.sha1(nickname.encode('utf-8')).hexdigest()[:10]}" if nickname else "live-pending"
        events.append(
            VirtualCustomerEvent(
                id=event_id,
                session_id=session_id,
                customer_id=customer_id,
                customer_nickname=nickname,
                customer_level="真实弹幕",
                event_type=event_type,
                content=content,
                trigger_reason="手机截图弹幕 OCR",
                priority=1,
                created_at=created_at,
            )
        )

    return events


def dedupe_live_comment_events(session_id: str, events: Iterable[VirtualCustomerEvent]) -> list[VirtualCustomerEvent]:
    seen = _seen_comment_signatures.setdefault(session_id, set())
    order = _seen_comment_order.setdefault(session_id, [])
    seen_texts = _seen_comment_texts.setdefault(session_id, [])
    fresh: list[VirtualCustomerEvent] = []

    for event in events:
        if not _is_publishable_live_comment(event):
            _remember_pending_live_comment(session_id, event)
            continue

        pending_event = _find_pending_live_comment(session_id, event)
        if pending_event:
            _remove_pending_live_comment(session_id, pending_event)
            refined_event = _refine_existing_live_comment(pending_event, event) or event
            _mark_comment_seen(refined_event, seen, order, seen_texts)
            fresh.append(refined_event)
            continue

        signature = _comment_signature(event.customer_nickname, event.content, event.event_type)
        semantic_text = _semantic_comment_text(event.content)
        semantic_key = f"{event.event_type}|{semantic_text}"
        existing_event = _find_existing_live_comment(session_id, event)
        if signature in seen or _has_seen_similar_text(semantic_key, seen_texts) or existing_event:
            refined_event = _refine_existing_live_comment(existing_event, event) if existing_event else None
            if refined_event:
                fresh.append(refined_event)
            continue
        _mark_comment_seen(event, seen, order, seen_texts)
        fresh.append(event)

    while len(order) > MAX_SEEN_SIGNATURES_PER_SESSION:
        stale = order.pop(0)
        seen.discard(stale)
    del seen_texts[: max(0, len(seen_texts) - MAX_SEEN_SIGNATURES_PER_SESSION)]

    return fresh


def extract_ocr_lines(payload: dict[str, Any]) -> list[str]:
    data: Any = payload.get("Data") or payload.get("data") or payload
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = {"content": data}

    lines: list[str] = []
    if isinstance(data, dict):
        content = data.get("content") or data.get("Content") or data.get("text") or ""
        if isinstance(content, str):
            lines.extend(_split_ocr_text(content))

        words_info = (
            data.get("prism_wordsInfo")
            or data.get("wordsInfo")
            or data.get("WordsInfo")
            or data.get("wordInfo")
            or []
        )
        if isinstance(words_info, list):
            for item in words_info:
                if not isinstance(item, dict):
                    continue
                word = item.get("word") or item.get("text") or item.get("content") or ""
                if isinstance(word, str):
                    lines.extend(_split_ocr_text(word))

    return _unique_clean_lines(lines)


def _recognize_with_windows_ocr(image_bytes: bytes) -> list[str]:
    if sys.platform != "win32":
        raise WindowsOcrUnavailable("Windows OCR 仅支持 Windows 本机")

    powershell_exe = shutil.which("powershell") or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    if not Path(powershell_exe).exists():
        raise WindowsOcrUnavailable("未找到 powershell，无法调用 Windows OCR")

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(prefix="jlao-comment-ocr-", suffix=".jpg", delete=False) as temp_file:
            temp_file.write(image_bytes)
            temp_path = temp_file.name

        env = dict(os.environ)
        env["JLAO_OCR_IMAGE"] = temp_path
        completed = subprocess.run(
            [powershell_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", _WINDOWS_OCR_SCRIPT],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=20,
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout or "").strip()
            raise WindowsOcrUnavailable(message or f"Windows OCR 退出码：{completed.returncode}")

        return [line for line in completed.stdout.splitlines() if line.strip()]
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass


def _recognize_general_with_aliyun(image_bytes: bytes) -> dict[str, Any]:
    if not (ALIYUN_OCR_AK_ID and ALIYUN_OCR_AK_SECRET):
        raise AliyunOcrNotConfigured("阿里云 OCR 未配置：需要 ALIYUN_AK_ID/ALIYUN_AK_SECRET")

    try:
        from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.http import protocol_type
        from aliyunsdkcore.request import CommonRequest
    except ImportError as exc:
        raise AliyunOcrNotConfigured("缺少 aliyun-python-sdk-core，无法调用阿里云 OCR") from exc

    client = AcsClient(ALIYUN_OCR_AK_ID, ALIYUN_OCR_AK_SECRET, ALIYUN_OCR_REGION)
    request = CommonRequest()
    request.set_method("POST")
    request.set_protocol_type(protocol_type.HTTPS)
    request.set_domain(ALIYUN_OCR_ENDPOINT)
    request.set_version("2021-07-07")
    request.set_action_name("RecognizeGeneral")
    request.set_content_type("application/octet-stream")
    request.set_content(image_bytes)

    try:
        response = client.do_action_with_exception(request)
    except (ClientException, ServerException) as exc:
        raise RuntimeError(f"阿里云 OCR 调用失败：{sanitize_ocr_error(str(exc))}") from None

    text = response.decode("utf-8") if isinstance(response, bytes) else response
    payload = json.loads(text)
    if payload.get("Code") and payload.get("Code") != "OK":
        raise RuntimeError(f"阿里云 OCR 响应异常：{payload.get('Code')} {payload.get('Message') or ''}")
    return payload


def _read_comment_region_bytes(image_path: Path) -> bytes:
    return _read_comment_region_variants(image_path)[0]


def _read_comment_region_variants(image_path: Path) -> list[bytes]:
    try:
        from PIL import Image, ImageEnhance, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow 未安装，无法裁剪弹幕区域") from exc

    with Image.open(image_path) as image:
        image = image.convert("RGB")
        width, height = image.size
        boxes = [
            (0, int(height * 0.52), int(width * 0.94), int(height * 0.93)),
            (0, int(height * 0.58), int(width * 0.98), int(height * 0.96)),
            (0, int(height * 0.45), int(width * 0.90), int(height * 0.90)),
        ]
        variants: list[bytes] = []
        for crop_box in boxes:
            crop = image.crop(crop_box)
            crop = ImageOps.autocontrast(crop)
            crop = ImageEnhance.Sharpness(crop).enhance(1.7)
            if crop.width < 900:
                crop = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)

            output = io.BytesIO()
            crop.save(output, format="JPEG", quality=90, optimize=True)
            variants.append(output.getvalue())
        return variants


def _parse_comment_line(raw_line: str) -> tuple[str, str, str] | None:
    line = _clean_line(raw_line)
    if not line or len(line) < 3:
        return None

    if "关注了主播" in line:
        nickname = _clean_nickname(line.split("关注了主播", 1)[0])
        if not nickname:
            return None
        return nickname, "关注了主播", "关注"

    has_comment_marker = "：" in line or ":" in line
    is_badged_line = bool(_BADGED_LINE_PATTERN.match(line))
    is_masked_line = bool(_MASKED_NICKNAME_PATTERN.match(line))
    if not has_comment_marker and not is_badged_line and not is_masked_line:
        if _looks_like_content_only_comment(line):
            return "", _clean_content(line), "弹幕"
        return None
    if _is_noise_line(line):
        return None

    match = _COMMENT_SPLIT_PATTERN.match(line)
    if match:
        nickname = _clean_nickname(match.group(1))
        content = _clean_content(match.group(2))
    else:
        match = _BADGED_LINE_PATTERN.match(line) or _MASKED_NICKNAME_PATTERN.match(line)
        if not match:
            return None
        nickname = _clean_nickname(match.group(1))
        content = _clean_content(match.group(2))

    if not nickname or not _is_valid_comment_content(content):
        return None
    return nickname, content, "弹幕"


def _clean_line(value: str) -> str:
    line = value.replace("\u3000", " ")
    line = re.sub(r"\s+", " ", line).strip()
    line = re.sub(r"\s*\*\s*\*", "**", line)
    line = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", line)
    line = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[，。？！；、,.!?;:：])", "", line)
    line = re.sub(r"(?<=[，。？！；、,.!?;:：])\s+(?=[\u4e00-\u9fff])", "", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line.strip("·|,，。[]【】()（）")


def _clean_nickname(value: str) -> str:
    nickname = _BADGE_PATTERN.sub("", _clean_line(value))
    nickname = re.sub(r"^[^\w\u4e00-\u9fff*]+", "", nickname)
    nickname = re.sub(r"[^\w\u4e00-\u9fff*.-]+$", "", nickname)
    nickname = re.sub(r"\s*\*\s*", "*", nickname)
    nickname = re.sub(r"^[0-9Oo零一二三四五六七八九十\s·._-]+(?=[A-Za-z\u4e00-\u9fff])", "", nickname)
    nickname = nickname.strip()
    if len(nickname) > 16:
        nickname = nickname[:16]
    if nickname == "未知观众":
        return ""
    return nickname


def _clean_content(value: str) -> str:
    content = _clean_line(value)
    content = re.sub(r"\b0@", "@", content)
    content = re.sub(r"^[0-9A-Za-z@\s·.'\"“”‘’*《》、，。；;:：-]+(?=[\u4e00-\u9fff])", "", content)
    return content


def _is_valid_comment_content(content: str) -> bool:
    if len(content) < 2:
        return False
    if len(content) > 120:
        return False
    return len(_semantic_comment_text(content)) >= 3


def _is_noise_line(line: str) -> bool:
    if "关注了主播" in line:
        return False
    if _BADGED_LINE_PATTERN.match(line):
        return False
    if _MASKED_NICKNAME_PATTERN.match(line):
        return False
    return any(marker in line for marker in _IGNORE_MARKERS)


def _candidate_comment_lines(lines: Iterable[str]) -> list[str]:
    candidates: list[str] = []
    pending = ""

    for raw_line in lines:
        line = _clean_line(raw_line)
        if not line:
            continue

        if _line_starts_comment(line):
            if pending:
                candidates.append(pending)
            pending = line
            continue

        if pending and _looks_like_continuation(line, pending):
            pending = f"{pending} {line}"
            continue

        if pending:
            candidates.append(pending)
            pending = ""

        if _looks_like_content_only_comment(line):
            candidates.append(line)

    if pending:
        candidates.append(pending)
    return candidates


def _line_starts_comment(line: str) -> bool:
    if "关注了主播" in line:
        return True
    if _COMMENT_SPLIT_PATTERN.match(line):
        return True
    if _BADGED_LINE_PATTERN.match(line):
        return True
    return bool(_MASKED_NICKNAME_PATTERN.match(line))


def _looks_like_continuation(line: str, pending: str) -> bool:
    if _line_starts_comment(line) or _is_noise_line(line):
        return False
    pending_parse = _parse_comment_line(pending)
    if not pending_parse or pending_parse[2] != "弹幕":
        return False
    pending_content = pending_parse[1]
    if len(pending_content) < 12 and not pending_content.endswith(("，", ",", "、", "；", ";")):
        return False
    if len(line) < 3 or len(line) > 80:
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", line))


def _looks_like_content_only_comment(line: str) -> bool:
    if _line_starts_comment(line) or _is_noise_line(line):
        return False
    if len(line) < 5 or len(line) > 80:
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", line))


def _split_ocr_text(text: str) -> list[str]:
    parts = re.split(r"[\r\n]+", text)
    return [part for part in parts if part.strip()]


def _unique_clean_lines(lines: Iterable[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for line in lines:
        cleaned = _clean_line(line)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        unique.append(cleaned)
    return unique


def _comment_signature(nickname: str, content: str, event_type: str) -> str:
    normalized = f"{event_type}|{nickname}|{_semantic_comment_text(content)}".casefold()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _semantic_comment_text(content: str) -> str:
    cleaned = _clean_content(content)
    return re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]", "", cleaned).casefold()


def _has_seen_similar_text(semantic_key: str, seen_texts: list[str]) -> bool:
    if len(semantic_key.split("|", 1)[-1]) < 5:
        return semantic_key in seen_texts
    for existing in seen_texts[-160:]:
        if _semantic_keys_are_similar(existing, semantic_key):
            return True
    return False


def _mark_comment_seen(
    event: VirtualCustomerEvent,
    seen: set[str],
    order: list[str],
    seen_texts: list[str],
) -> None:
    signature = _comment_signature(event.customer_nickname, event.content, event.event_type)
    if signature not in seen:
        seen.add(signature)
        order.append(signature)
    semantic_key = f"{event.event_type}|{_semantic_comment_text(event.content)}"
    if not _has_seen_similar_text(semantic_key, seen_texts):
        seen_texts.append(semantic_key)


def _is_publishable_live_comment(event: VirtualCustomerEvent) -> bool:
    if event.event_type == "关注":
        return bool(event.customer_nickname)
    return _nickname_score(event.customer_nickname) >= 3 and _is_valid_comment_content(event.content)


def _remember_pending_live_comment(session_id: str, candidate: VirtualCustomerEvent) -> None:
    if not _is_valid_comment_content(candidate.content):
        return

    pending_events = _pending_comment_events.setdefault(session_id, [])
    existing = _find_pending_live_comment(session_id, candidate)
    if existing:
        existing_text = _semantic_comment_text(existing.content)
        candidate_text = _semantic_comment_text(candidate.content)
        if len(candidate_text) > len(existing_text) and _semantic_texts_are_similar(existing_text, candidate_text):
            existing.content = candidate.content
        return

    pending_events.insert(0, candidate)
    del pending_events[MAX_PENDING_COMMENT_EVENTS_PER_SESSION:]


def _find_pending_live_comment(session_id: str, candidate: VirtualCustomerEvent) -> VirtualCustomerEvent | None:
    candidate_key = f"{candidate.event_type}|{_semantic_comment_text(candidate.content)}"
    for existing in _pending_comment_events.get(session_id, [])[:MAX_PENDING_COMMENT_EVENTS_PER_SESSION]:
        existing_key = f"{existing.event_type}|{_semantic_comment_text(existing.content)}"
        if _semantic_keys_are_similar(existing_key, candidate_key):
            return existing
    return None


def _remove_pending_live_comment(session_id: str, pending_event: VirtualCustomerEvent) -> None:
    pending_events = _pending_comment_events.get(session_id)
    if not pending_events:
        return
    _pending_comment_events[session_id] = [event for event in pending_events if event.id != pending_event.id]


def _find_existing_live_comment(session_id: str, candidate: VirtualCustomerEvent) -> VirtualCustomerEvent | None:
    candidate_key = f"{candidate.event_type}|{_semantic_comment_text(candidate.content)}"
    for existing in app_state.live_comments.get(session_id, [])[:MAX_LIVE_COMMENTS_PER_SESSION]:
        existing_key = f"{existing.event_type}|{_semantic_comment_text(existing.content)}"
        if _semantic_keys_are_similar(existing_key, candidate_key):
            return existing
    return None


def _refine_existing_live_comment(
    existing: VirtualCustomerEvent | None,
    candidate: VirtualCustomerEvent,
) -> VirtualCustomerEvent | None:
    if existing is None:
        return None

    changed = False
    if _nickname_score(candidate.customer_nickname) > _nickname_score(existing.customer_nickname):
        existing.customer_nickname = candidate.customer_nickname
        existing.customer_id = candidate.customer_id
        changed = True

    existing_text = _semantic_comment_text(existing.content)
    candidate_text = _semantic_comment_text(candidate.content)
    if len(candidate_text) > len(existing_text) and _semantic_texts_are_similar(existing_text, candidate_text):
        existing.content = candidate.content
        changed = True

    return existing if changed else None


def _semantic_keys_are_similar(left: str, right: str) -> bool:
    left_type, left_text = left.split("|", 1)
    right_type, right_text = right.split("|", 1)
    return left_type == right_type and _semantic_texts_are_similar(left_text, right_text)


def _semantic_texts_are_similar(left_text: str, right_text: str) -> bool:
    if not left_text or not right_text:
        return False
    if left_text in right_text or right_text in left_text:
        return True
    return SequenceMatcher(a=left_text, b=right_text).ratio() >= 0.88


def _nickname_score(nickname: str) -> int:
    cleaned = _clean_nickname(nickname)
    compact = re.sub(r"\s+", "", cleaned)
    if not compact or compact == "未知观众":
        return 0
    if not re.search(r"[A-Za-z\u4e00-\u9fff]", compact):
        return 1
    if re.search(r"[《》“”‘’·、，。；;:：]", compact):
        return 2
    if re.fullmatch(r"[A-Za-z\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff.-]*\*{0,3}", compact):
        return 4
    return 3


def _lock_for_session(session_id: str) -> asyncio.Lock:
    lock = _session_ocr_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _session_ocr_locks[session_id] = lock
    return lock


def _should_scan_now(session_id: str) -> bool:
    last_scan_at = _session_last_ocr_at.get(session_id, 0)
    return time.monotonic() - last_scan_at >= COMMENT_OCR_INTERVAL_SECONDS


def _warn_ocr_not_configured(message: str) -> None:
    global _warned_not_configured
    if _warned_not_configured:
        return
    _warned_not_configured = True
    logger.warning(message)


def sanitize_ocr_error(message: str) -> str:
    return _SENSITIVE_QUERY_PATTERN.sub(lambda match: f"{match.group(1)}=<redacted>", message)


def _update_ocr_status(session_id: str, **fields: Any) -> None:
    status = app_state.live_comment_ocr_status.setdefault(session_id, {})
    status.update(fields)
    status["updated_at"] = datetime.now(timezone.utc).isoformat()
