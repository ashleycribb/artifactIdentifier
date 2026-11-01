"""Tests for deterministic classification engine and taxonomy rules."""

from pathlib import Path
from src.classifier.engine import ClassificationEngine
from src.config import AppConfig


def test_heterogeneous_artifact_classification(mock_workspace: Path):
    config = AppConfig()
    config.user_profile.author_names = ["Ashley Smith", "Ashley"]
    engine = ClassificationEngine(config)

    # 1. Scholarly HTML -> AcademicPaper
    html_manifest = engine.classify_file(mock_workspace / "scalable_ontologies.html", mock_workspace)
    assert html_manifest is not None
    assert html_manifest["classification"]["class"] == "AcademicPaper"
    assert html_manifest["classification"]["confidence"] >= 0.90

    # 2. Markdown Notes -> ResearchNote
    note_manifest = engine.classify_file(mock_workspace / "meeting_notes_2026.md", mock_workspace)
    assert note_manifest is not None
    assert note_manifest["classification"]["class"] == "ResearchNote"

    # 3. Compound Tarball -> SourcePackage
    tar_manifest = engine.classify_file(mock_workspace / "arXiv-2607.02514v1.tar.gz", mock_workspace)
    assert tar_manifest is not None
    assert tar_manifest["classification"]["class"] == "SourcePackage"

    # 4. Large Poster PDF -> ConferencePoster
    poster_manifest = engine.classify_file(mock_workspace / "poster_symposium_2026.pdf", mock_workspace)
    assert poster_manifest is not None
    assert poster_manifest["classification"]["class"] == "ConferencePoster"

    # 5. Slide Deck PDF -> ConferencePresentation
    slides_manifest = engine.classify_file(mock_workspace / "seminar_deck.pdf", mock_workspace)
    assert slides_manifest is not None
    assert slides_manifest["classification"]["class"] == "ConferencePresentation"

    # 6. Child Figure in Draft -> Excluded (None)
    fig_manifest = engine.classify_file(mock_workspace / "draft_project" / "figures" / "fig1.pdf", mock_workspace)
    assert fig_manifest is None

    # 7. Author Draft LaTeX -> AuthorDraft
    tex_manifest = engine.classify_file(mock_workspace / "draft_project" / "main.tex", mock_workspace)
    assert tex_manifest is not None
    assert tex_manifest["classification"]["class"] == "AuthorDraft"
