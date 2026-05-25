import hashlib
import os
import re
from datetime import datetime
from pathlib import Path

from app.repositories import list_wiki_chunks, replace_wiki_chunks
from app.schemas import WikiChunk
from app.state import WORKSPACE_DIR


DEFAULT_WIKI_PATH = Path(r"C:\Users\chuyu\Desktop\wiki.md")
FALLBACK_WIKI_PATH = WORKSPACE_DIR / "data" / "samples" / "wiki.md"


def configured_wiki_path() -> Path:
    value = os.getenv("JLAO_WIKI_PATH")
    return Path(value) if value else DEFAULT_WIKI_PATH


def parse_markdown_chunks(markdown: str, source_path: str = "wiki.md") -> list[WikiChunk]:
    chunks: list[WikiChunk] = []
    current_heading = "未命名章节"
    current_lines: list[str] = []

    def flush() -> None:
        content = "\n".join(line.strip() for line in current_lines).strip()
        if not content:
            return
        digest = hashlib.sha1(f"{source_path}:{current_heading}:{content}".encode("utf-8")).hexdigest()[:12]
        chunks.append(
            WikiChunk(
                id=f"wiki-{digest}",
                source_path=source_path,
                heading=current_heading,
                content=content,
                tags=_infer_tags(current_heading, content),
                updated_at=datetime.utcnow(),
            )
        )

    for raw_line in markdown.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", raw_line)
        if match:
            flush()
            current_heading = match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(raw_line)

    flush()
    return chunks


def search_wiki_chunks(chunks: list[WikiChunk], query: str, limit: int = 5) -> list[WikiChunk]:
    terms = [term for term in re.split(r"[\s,，。；;、]+", query.strip()) if term]
    if not terms:
        return chunks[:limit]

    scored: list[tuple[int, WikiChunk]] = []
    for chunk in chunks:
        haystack = f"{chunk.heading}\n{chunk.content}\n{' '.join(chunk.tags)}"
        score = 0
        for term in terms:
            if term in chunk.heading:
                score += 4
            score += haystack.count(term)
        if score:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored[:limit]]


def load_wiki_file() -> tuple[Path, str]:
    primary = configured_wiki_path()
    if primary.exists():
        return primary, primary.read_text(encoding="utf-8")
    if FALLBACK_WIKI_PATH.exists():
        return FALLBACK_WIKI_PATH, FALLBACK_WIKI_PATH.read_text(encoding="utf-8")
    return primary, ""


def reload_wiki_chunks() -> list[WikiChunk]:
    path, markdown = load_wiki_file()
    chunks = parse_markdown_chunks(markdown, source_path=str(path)) if markdown else []
    replace_wiki_chunks(chunks)
    return chunks


def get_indexed_wiki_chunks() -> list[WikiChunk]:
    chunks = list_wiki_chunks()
    if chunks:
        return chunks
    return reload_wiki_chunks()


def search_indexed_wiki(query: str, limit: int = 5) -> list[WikiChunk]:
    return search_wiki_chunks(get_indexed_wiki_chunks(), query, limit=limit)


def _infer_tags(heading: str, content: str) -> list[str]:
    text = f"{heading}\n{content}"
    tags: list[str] = []
    for tag, keywords in {
        "风控": ["禁忌", "风控", "保证", "升值", "绝对"],
        "商品": ["翡翠", "种水", "颜色", "证书", "瑕疵"],
        "售后": ["售后", "退换", "复检", "发货"],
        "话术": ["话术", "欢迎", "互动", "促单"],
        "客户": ["客户", "老客", "偏好", "关系"],
    }.items():
        if any(keyword in text for keyword in keywords):
            tags.append(tag)
    return tags
