"""Unified multi-format text and title block extraction module."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import List, Optional

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None  # type: ignore

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore

try:
    import docx
except ImportError:
    docx = None  # type: ignore

try:
    from pptx import Presentation
except ImportError:
    Presentation = None  # type: ignore


@dataclass
class ExtractedTextResult:
    format: str
    page_count: Optional[int] = None
    title: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    headings: List[str] = field(default_factory=list)
    text_snippet: str = ""
    token_count: int = 0
    meta_tags: dict = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    """Rough estimation of token count (~4 chars per token)."""
    return max(1, len(text) // 4) if text else 0


def extract_document_text(path: str | Path, max_tokens: int = 2048) -> ExtractedTextResult:
    """Extracts text, metadata, headings, and structure from a supported document file."""
    file_path = Path(path)
    if not file_path.is_file():
        return ExtractedTextResult(format="unknown", text_snippet="File not found")

    ext = file_path.suffix.lower()

    if ext == ".pdf":
        return _extract_pdf(file_path, max_tokens)
    elif ext in (".docx", ".doc"):
        return _extract_docx(file_path, max_tokens)
    elif ext in (".pptx", ".ppt"):
        return _extract_pptx(file_path, max_tokens)
    elif ext in (".html", ".htm"):
        return _extract_html(file_path, max_tokens)
    elif ext in (".tex", ".latex"):
        return _extract_tex(file_path, max_tokens)
    elif ext in (".md", ".txt", ".org", ".rst"):
        return _extract_markdown(file_path, max_tokens)
    else:
        return ExtractedTextResult(format=ext, text_snippet=f"Unsupported format: {ext}")


def _extract_pdf(path: Path, max_tokens: int) -> ExtractedTextResult:
    if PdfReader is None:
        return ExtractedTextResult(format="pdf", text_snippet="pypdf library unavailable")

    try:
        reader = PdfReader(str(path))
        page_count = len(reader.pages)
        title: Optional[str] = None
        authors: List[str] = []

        if reader.metadata:
            title = reader.metadata.title
            if reader.metadata.author:
                authors = [a.strip() for a in reader.metadata.author.split(",") if a.strip()]

        full_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text:
                full_text.append(text)
            if estimate_tokens(" ".join(full_text)) >= max_tokens:
                break

        combined = "\n\n".join(full_text)
        # Try to infer title from first line if metadata title is absent
        if not title and full_text:
            lines = [l.strip() for l in full_text[0].split("\n") if len(l.strip()) > 5]
            if lines:
                title = lines[0]

        return ExtractedTextResult(
            format="pdf",
            page_count=page_count,
            title=title,
            authors=authors,
            text_snippet=combined[: max_tokens * 4],
            token_count=estimate_tokens(combined),
        )
    except Exception as e:
        return ExtractedTextResult(format="pdf", text_snippet=f"PDF extraction error: {e}")


def _extract_docx(path: Path, max_tokens: int) -> ExtractedTextResult:
    if docx is None:
        return ExtractedTextResult(format="docx", text_snippet="python-docx library unavailable")

    try:
        doc = docx.Document(str(path))
        title = None
        headings: List[str] = []
        paragraphs: List[str] = []

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue
            if p.style and "heading" in p.style.name.lower():
                headings.append(text)
                if not title and ("title" in p.style.name.lower() or "heading 1" in p.style.name.lower()):
                    title = text
            else:
                paragraphs.append(text)
                if not title and len(text) < 120 and len(paragraphs) == 1:
                    title = text

            if estimate_tokens(" ".join(paragraphs)) >= max_tokens:
                break

        combined = "\n\n".join(paragraphs)
        return ExtractedTextResult(
            format="docx",
            page_count=None,
            title=title,
            headings=headings,
            text_snippet=combined[: max_tokens * 4],
            token_count=estimate_tokens(combined),
        )
    except Exception as e:
        return ExtractedTextResult(format="docx", text_snippet=f"DOCX extraction error: {e}")


def _extract_pptx(path: Path, max_tokens: int) -> ExtractedTextResult:
    if Presentation is None:
        return ExtractedTextResult(format="pptx", text_snippet="python-pptx library unavailable")

    try:
        prs = Presentation(str(path))
        slide_count = len(prs.slides)
        title: Optional[str] = None
        slide_texts: List[str] = []

        for i, slide in enumerate(prs.slides):
            texts_in_slide = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        t = paragraph.text.strip()
                        if t:
                            texts_in_slide.append(t)
            if texts_in_slide:
                slide_content = " | ".join(texts_in_slide)
                slide_texts.append(f"[Slide {i+1}] {slide_content}")
                if i == 0 and not title:
                    title = texts_in_slide[0]

            if estimate_tokens(" ".join(slide_texts)) >= max_tokens:
                break

        combined = "\n".join(slide_texts)
        return ExtractedTextResult(
            format="pptx",
            page_count=slide_count,
            title=title,
            text_snippet=combined[: max_tokens * 4],
            token_count=estimate_tokens(combined),
        )
    except Exception as e:
        return ExtractedTextResult(format="pptx", text_snippet=f"PPTX extraction error: {e}")


def _extract_html(path: Path, max_tokens: int) -> ExtractedTextResult:
    if BeautifulSoup is None:
        return ExtractedTextResult(format="html", text_snippet="BeautifulSoup unavailable")

    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        # Extract Scholarly HTML meta tags
        meta_tags: dict = {}
        authors: List[str] = []
        for tag in soup.find_all("meta"):
            name = (tag.get("name") or tag.get("property") or "").lower()
            content = tag.get("content", "")
            if name and content:
                meta_tags[name] = content
                if name in ("citation_author", "dc.creator"):
                    authors.append(content)

        title = None
        if "citation_title" in meta_tags:
            title = meta_tags["citation_title"]
        elif "dc.title" in meta_tags:
            title = meta_tags["dc.title"]
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Headings
        headings = [h.get_text().strip() for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text().strip()]

        # Body text
        text = soup.get_text(separator="\n", strip=True)
        return ExtractedTextResult(
            format="html",
            page_count=1,
            title=title,
            authors=authors,
            headings=headings,
            text_snippet=text[: max_tokens * 4],
            token_count=estimate_tokens(text),
            meta_tags=meta_tags,
        )
    except Exception as e:
        return ExtractedTextResult(format="html", text_snippet=f"HTML extraction error: {e}")


def _extract_tex(path: Path, max_tokens: int) -> ExtractedTextResult:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        title = None
        title_match = re.search(r"\\title\s*\{([^}]+)\}", content)
        if title_match:
            title = title_match.group(1).strip()

        authors: List[str] = []
        author_match = re.search(r"\\author\s*\{([^}]+)\}", content)
        if author_match:
            authors = [a.strip() for a in re.split(r"\\and|,", author_match.group(1)) if a.strip()]

        # Clean LaTeX commands roughly for snippet
        cleaned = re.sub(r"%.*", "", content)
        cleaned = re.sub(r"\\[a-zA-Z]+(\[[^\]]*\])?(\{([^}]*)\})?", r" \3 ", cleaned)

        return ExtractedTextResult(
            format="tex",
            page_count=None,
            title=title,
            authors=authors,
            text_snippet=cleaned[: max_tokens * 4],
            token_count=estimate_tokens(cleaned),
        )
    except Exception as e:
        return ExtractedTextResult(format="tex", text_snippet=f"TeX extraction error: {e}")


def _extract_markdown(path: Path, max_tokens: int) -> ExtractedTextResult:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        title = None
        headings: List[str] = []
        lines = content.splitlines()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                headings.append(stripped)
                if not title:
                    title = stripped[2:].strip()
            elif stripped.startswith("## ") or stripped.startswith("### "):
                headings.append(stripped)

        return ExtractedTextResult(
            format="markdown",
            page_count=None,
            title=title,
            headings=headings,
            text_snippet=content[: max_tokens * 4],
            token_count=estimate_tokens(content),
        )
    except Exception as e:
        return ExtractedTextResult(format="markdown", text_snippet=f"Markdown extraction error: {e}")
