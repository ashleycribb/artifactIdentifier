"""Pytest fixtures for research artifact classifier testing."""

import io
from pathlib import Path
import tarfile
import pytest

from pypdf import PdfWriter


@pytest.fixture
def mock_workspace(tmp_path: Path) -> Path:
    """Generates a realistic heterogeneous research workspace."""
    ws = tmp_path / "research_vault"
    ws.mkdir()

    # 1. Scholarly HTML Preprint
    html_file = ws / "scalable_ontologies.html"
    html_file.write_text(
        """<!DOCTYPE html>
<html>
<head>
    <meta name="citation_title" content="Scalable Ontology Alignment for Autonomous Swarms">
    <meta name="citation_author" content="Dr. Ashley Smith">
    <meta name="citation_author" content="Dr. Jane Doe">
    <meta name="citation_doi" content="10.1145/3318464.3389700">
    <meta name="citation_journal_title" content="Journal of Autonomous Systems">
    <title>Scalable Ontology Alignment</title>
</head>
<body>
    <h1>Scalable Ontology Alignment for Autonomous Swarms</h1>
    <p>Abstract: We introduce dual-plane governance models...</p>
</body>
</html>
""",
        encoding="utf-8",
    )

    # 2. Markdown Research Note
    note_file = ws / "meeting_notes_2026.md"
    note_file.write_text(
        """# Meeting Notes: S3A Ingestion Pipeline
Date: 2026-11-01
Attendees: Ashley, Architecture Team

Discussed removal of DuckDB and SQLite. Hyper-Tiles 10-15 provide zero-db binary architecture.
Next steps: implement fast-path rules and xAPI logger.
""",
        encoding="utf-8",
    )

    # 3. LaTeX Author Draft Project
    draft_dir = ws / "draft_project"
    draft_dir.mkdir()
    tex_file = draft_dir / "main.tex"
    tex_file.write_text(
        r"""\documentclass{article}
\title{Autonomous Classifier Verification}
\author{Ashley Smith}
\begin{document}
\maketitle
Draft version under review.
\end{document}
""",
        encoding="utf-8",
    )

    # Sub-asset figure inside draft project
    figures_dir = draft_dir / "figures"
    figures_dir.mkdir()
    fig1 = figures_dir / "fig1.pdf"
    # Create minimal valid PDF
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    with fig1.open("wb") as f:
        writer.write(f)

    # 4. Standalone Conference Poster PDF (36" x 48" = 2592 x 3456 pt)
    poster_file = ws / "poster_symposium_2026.pdf"
    p_writer = PdfWriter()
    p_writer.add_blank_page(width=2592, height=3456)
    with poster_file.open("wb") as f:
        p_writer.write(f)

    # 5. Standalone Slide Deck PDF (16:9 ratio, 5 pages)
    slides_file = ws / "seminar_deck.pdf"
    s_writer = PdfWriter()
    for _ in range(5):
        s_writer.add_blank_page(width=960, height=540)  # 16:9 ratio
    with slides_file.open("wb") as f:
        s_writer.write(f)

    # 6. Compound Archive (.tar.gz)
    archive_file = ws / "arXiv-2607.02514v1.tar.gz"
    with tarfile.open(archive_file, "w:gz") as tar:
        # Add a dummy main.tex
        tex_bytes = b"\\documentclass{article}\\title{Compound Archive}\\begin{document}Hello\\end{document}"
        ti = tarfile.TarInfo(name="main.tex")
        ti.size = len(tex_bytes)
        tar.addfile(ti, io.BytesIO(tex_bytes))

        # Add a dummy figure
        fig_bytes = b"%PDF-1.4 dummy figure content"
        ti_fig = tarfile.TarInfo(name="figures/plot.pdf")
        ti_fig.size = len(fig_bytes)
        tar.addfile(ti_fig, io.BytesIO(fig_bytes))

    return ws
