"""Tests for extraction modules: text, geometry, archive, and bibliographic."""

from pathlib import Path
from src.extractors.archive import inspect_archive, is_sub_asset_file
from src.extractors.bibliographic import extract_bibliographic_metadata
from src.extractors.geometry import analyze_pdf_geometry
from src.extractors.text import extract_document_text


def test_archive_introspection(mock_workspace: Path):
    tar_path = mock_workspace / "arXiv-2607.02514v1.tar.gz"
    res = inspect_archive(tar_path)
    assert res.is_valid is True
    assert res.archive_format == "tar.gz"
    assert res.root_manuscript == "main.tex"
    assert any("figures/plot.pdf" in f for f in res.asset_files)


def test_sub_asset_file_exclusion(mock_workspace: Path):
    fig_path = mock_workspace / "draft_project" / "figures" / "fig1.pdf"
    assert is_sub_asset_file(fig_path, mock_workspace) is True

    # Standalone poster is not a sub-asset
    poster_path = mock_workspace / "poster_symposium_2026.pdf"
    assert is_sub_asset_file(poster_path, mock_workspace) is False


def test_geometry_analysis(mock_workspace: Path):
    poster_path = mock_workspace / "poster_symposium_2026.pdf"
    geo_poster = analyze_pdf_geometry(poster_path)
    assert geo_poster.is_poster_candidate is True
    assert geo_poster.is_slide_deck_candidate is False
    assert geo_poster.dimension.width >= 24.0

    slides_path = mock_workspace / "seminar_deck.pdf"
    geo_slides = analyze_pdf_geometry(slides_path)
    assert geo_slides.is_slide_deck_candidate is True
    assert geo_slides.is_poster_candidate is False
    assert geo_slides.aspect_ratio_label == "16:9"


def test_text_and_bibliographic_extraction(mock_workspace: Path):
    html_path = mock_workspace / "scalable_ontologies.html"
    text_res = extract_document_text(html_path)
    assert text_res.title == "Scalable Ontology Alignment for Autonomous Swarms"
    assert "Dr. Ashley Smith" in text_res.authors

    bib_res = extract_bibliographic_metadata(
        text=text_res.text_snippet,
        meta_tags=text_res.meta_tags,
    )
    assert bib_res.doi == "10.1145/3318464.3389700"
    assert bib_res.has_scholarly_metadata is True
