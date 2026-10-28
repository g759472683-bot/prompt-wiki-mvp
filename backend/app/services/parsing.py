from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


class ParseError(Exception):
    """Raised when a document cannot be turned into usable blocks."""


@dataclass
class ParsedBlock:
    page: int
    start: int
    end: int
    text: str


@dataclass
class ParseResult:
    blocks: list[ParsedBlock]
    pages: int
    parser: str
    parser_version: str
    warnings: list[dict] = field(default_factory=list)


def _pkg_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def _split_paragraphs(text: str) -> list[tuple[int, int, str]]:
    """Split on blank lines, preserving offsets in the original text."""
    out: list[tuple[int, int, str]] = []
    cursor = 0
    for part in re.split(r"\n\s*\n", text):
        stripped = part.strip()
        if not stripped:
            cursor += len(part)
            continue
        start = text.find(stripped, cursor)
        if start < 0:
            start = text.find(stripped)
        if start < 0:
            continue
        end = start + len(stripped)
        out.append((start, end, stripped))
        cursor = end
    return out


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParseError("无法识别文本编码，请另存为 UTF-8 后重试")


def _parse_pdf(path: Path) -> ParseResult:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - dependency is installed in prod
        raise ParseError("PDF 解析依赖未安装：pip install pdfplumber") from exc

    blocks: list[ParsedBlock] = []
    warnings: list[dict] = []
    pages = 0
    with pdfplumber.open(str(path)) as pdf:
        pages = len(pdf.pages)
        for page_no, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                warnings.append(
                    {
                        "code": "EMPTY_PAGE",
                        "message": f"第 {page_no} 页没有可提取文本（可能是扫描件）",
                    }
                )
                continue
            for start, end, chunk in _split_paragraphs(text):
                blocks.append(ParsedBlock(page=page_no, start=start, end=end, text=chunk))

    if not blocks:
        raise ParseError("PDF 没有可提取文本（可能是扫描件，请先 OCR）")
    return ParseResult(
        blocks=blocks,
        pages=pages,
        parser="pdfplumber",
        parser_version=_pkg_version("pdfplumber"),
        warnings=warnings,
    )


def _parse_docx(path: Path) -> ParseResult:
    try:
        from docx import Document as DocxDocument
    except ImportError as exc:  # pragma: no cover
        raise ParseError("Word 解析依赖未安装：pip install python-docx") from exc

    doc = DocxDocument(str(path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    if not paragraphs:
        raise ParseError("Word 文档里没有可提取的段落")
    text = "\n\n".join(paragraphs)
    blocks = [
        ParsedBlock(page=1, start=start, end=end, text=chunk)
        for start, end, chunk in _split_paragraphs(text)
    ]
    return ParseResult(
        blocks=blocks,
        pages=1,
        parser="python-docx",
        parser_version=_pkg_version("python-docx"),
    )


def _parse_text(path: Path) -> ParseResult:
    text = _read_text(path)
    blocks = [
        ParsedBlock(page=1, start=start, end=end, text=chunk)
        for start, end, chunk in _split_paragraphs(text)
    ]
    if not blocks:
        raise ParseError("文件里没有可提取的段落")
    return ParseResult(
        blocks=blocks,
        pages=1,
        parser="plaintext",
        parser_version="1",
    )


def parse_document(path: Path, filename: str) -> ParseResult:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(path)
    if suffix == ".docx":
        return _parse_docx(path)
    if suffix in {".txt", ".md", ".markdown"}:
        return _parse_text(path)
    raise ParseError(f"不支持的文件类型：{suffix or '(无扩展名)'}")
