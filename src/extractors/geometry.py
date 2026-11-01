"""Layout, mediabox dimensions, and aspect ratio inspector."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore


@dataclass
class DimensionInfo:
    width: float
    height: float
    unit: str  # "in", "mm", "pt"
    aspect_ratio: float
    is_landscape: bool
    page_count: int


@dataclass
class GeometryAnalysisResult:
    has_geometry: bool
    dimension: Optional[DimensionInfo] = None
    is_poster_candidate: bool = False
    is_slide_deck_candidate: bool = False
    aspect_ratio_label: str = "custom"
    summary: str = ""


# Point conversions
POINTS_PER_INCH = 72.0
POSTER_MIN_DIMENSION_INCHES = 24.0  # 610 mm


def analyze_pdf_geometry(path: str | Path) -> GeometryAnalysisResult:
    """Inspects PDF page geometry to identify posters (>= 24 in) and slide decks."""
    if PdfReader is None:
        return GeometryAnalysisResult(has_geometry=False, summary="pypdf not available")

    file_path = Path(path)
    if not file_path.is_file():
        return GeometryAnalysisResult(has_geometry=False, summary="File not found")

    try:
        reader = PdfReader(str(file_path))
        page_count = len(reader.pages)
        if page_count == 0:
            return GeometryAnalysisResult(has_geometry=False, summary="PDF has 0 pages")

        first_page = reader.pages[0]
        mb = first_page.mediabox
        width_pt = float(mb.width)
        height_pt = float(mb.height)

        width_in = width_pt / POINTS_PER_INCH
        height_in = height_pt / POINTS_PER_INCH

        is_landscape = width_pt > height_pt
        ratio = width_pt / height_pt if height_pt > 0 else 1.0

        # Detect standard slide aspect ratios
        ratio_label = "custom"
        if 1.70 <= ratio <= 1.85:
            ratio_label = "16:9"
        elif 1.30 <= ratio <= 1.36:
            ratio_label = "4:3"
        elif 1.55 <= ratio <= 1.65:
            ratio_label = "16:10"

        # Poster check: single page with either dimension >= 24 inches
        is_poster = (
            page_count == 1
            and (width_in >= POSTER_MIN_DIMENSION_INCHES or height_in >= POSTER_MIN_DIMENSION_INCHES)
        )

        # Slide deck check: >= 3 pages with presentation aspect ratio and standard landscape orientation
        is_slide_deck = (
            page_count >= 3
            and is_landscape
            and ratio_label in ("16:9", "4:3", "16:10")
        )

        dim_info = DimensionInfo(
            width=round(width_in, 2),
            height=round(height_in, 2),
            unit="in",
            aspect_ratio=round(ratio, 3),
            is_landscape=is_landscape,
            page_count=page_count,
        )

        summary = (
            f"{page_count} page(s), {dim_info.width}\" x {dim_info.height}\" ({ratio_label}). "
            f"Poster: {is_poster}, SlideDeck: {is_slide_deck}."
        )

        return GeometryAnalysisResult(
            has_geometry=True,
            dimension=dim_info,
            is_poster_candidate=is_poster,
            is_slide_deck_candidate=is_slide_deck,
            aspect_ratio_label=ratio_label,
            summary=summary,
        )
    except Exception as e:
        return GeometryAnalysisResult(has_geometry=False, summary=f"Geometry inspection failed: {e}")
