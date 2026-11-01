"""Tests for catalog management, overrides, and S3A staging bridge."""

from pathlib import Path
from src.catalog.manager import CatalogManager
from src.classifier.engine import ClassificationEngine
from src.config import AppConfig
from src.s3a.bridge import S3ABridge


def test_catalog_and_human_override(mock_workspace: Path, tmp_path: Path):
    meta_dir = tmp_path / ".s3a" / "metadata"
    catalog = CatalogManager(meta_dir)

    engine = ClassificationEngine(AppConfig())
    manifest = engine.classify_file(mock_workspace / "scalable_ontologies.html")
    assert manifest is not None

    # Save manifest
    ok, err = catalog.save_manifest(manifest)
    assert ok is True
    assert err is None

    sha256 = manifest["fingerprint"]["sha256"]
    retrieved = catalog.get_manifest(sha256)
    assert retrieved is not None
    assert retrieved["fingerprint"]["sha256"] == sha256

    # Apply valid override
    override_ok, override_err = catalog.apply_override(
        sha256=sha256,
        new_class="ResearchNote",
        user_name="researcher_ashley",
        notes="Reclassifying to note",
    )
    assert override_ok is True

    updated = catalog.get_manifest(sha256)
    assert updated["classification"]["class"] == "ResearchNote"
    assert updated["human_override"]["active"] is True
    assert updated["human_override"]["original_class"] == "AcademicPaper"
    assert updated["human_override"]["updated_by"] == "researcher_ashley"

    # Invalid class rejected
    inv_ok, inv_err = catalog.apply_override(
        sha256=sha256,
        new_class="NonExistentClass",
        user_name="researcher_ashley",
    )
    assert inv_ok is False


def test_s3a_staging_bridge(mock_workspace: Path, tmp_path: Path):
    meta_dir = tmp_path / ".s3a" / "metadata"
    staging_dir = tmp_path / ".s3a" / "staging"
    catalog = CatalogManager(meta_dir)

    engine = ClassificationEngine(AppConfig())
    manifest = engine.classify_file(mock_workspace / "scalable_ontologies.html")
    catalog.save_manifest(manifest)

    bridge = S3ABridge(staging_dir=staging_dir)
    counts = bridge.stage_ingestion(catalog)

    assert counts["academic_papers"] == 1
    assert counts["ai_traces"] == 1
    assert (staging_dir / "academic_papers.jsonl").exists()
    assert (staging_dir / "workspace.json").exists()
