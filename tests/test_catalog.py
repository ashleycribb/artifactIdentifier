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
    assert updated["confirmation"]["status"] == "overridden"
    assert updated["confirmation"]["final_class"] == "ResearchNote"
    assert updated["classification"]["suggested_class"] == "AcademicPaper"  # agent suggestion preserved
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


def _saved_manifest(mock_workspace: Path, tmp_path: Path, name: str = "scalable_ontologies.html"):
    catalog = CatalogManager(tmp_path / ".s3a" / "metadata")
    manifest = ClassificationEngine(AppConfig()).classify_file(mock_workspace / name)
    assert catalog.save_manifest(manifest)[0]
    return catalog, manifest["fingerprint"]["sha256"]


def test_classifier_output_is_only_a_suggestion(mock_workspace: Path, tmp_path: Path):
    catalog, sha = _saved_manifest(mock_workspace, tmp_path)
    m = catalog.get_manifest(sha)
    assert m["classification"]["suggested_class"] == "AcademicPaper"
    assert 0.0 <= m["classification"]["confidence"] <= 1.0
    assert "class" not in m["classification"]
    assert m["confirmation"] == {
        "status": "unconfirmed", "final_class": None, "confirmed_by": None, "confirmed_at": None, "notes": None,
    }


def test_confirm_makes_suggestion_final(mock_workspace: Path, tmp_path: Path):
    catalog, sha = _saved_manifest(mock_workspace, tmp_path)
    ok, err = catalog.confirm(sha, "ashley", "looks right")
    assert ok, err
    m = catalog.get_manifest(sha)
    assert m["confirmation"]["status"] == "confirmed"
    assert m["confirmation"]["final_class"] == "AcademicPaper"
    assert m["confirmation"]["confirmed_by"] == "ashley"


def test_confirm_requires_identity_and_known_sha(mock_workspace: Path, tmp_path: Path):
    catalog, sha = _saved_manifest(mock_workspace, tmp_path)
    assert catalog.confirm(sha, "  ")[0] is False
    assert catalog.confirm("0" * 64, "ashley")[0] is False


def test_needs_review_cannot_be_confirmed_only_overridden(tmp_path: Path):
    catalog = CatalogManager(tmp_path / ".s3a" / "metadata")
    f = tmp_path / "mystery.bin"
    f.write_bytes(b"\x00\x01\x02 ambiguous")
    manifest = ClassificationEngine(AppConfig()).classify_file(f)
    assert manifest["classification"]["suggested_class"] == "NeedsReview"
    catalog.save_manifest(manifest)
    sha = manifest["fingerprint"]["sha256"]
    ok, err = catalog.confirm(sha, "ashley")
    assert ok is False and "override" in err
    assert catalog.apply_override(sha, "ResearchNote", "ashley")[0] is True


def test_legacy_manifest_is_normalized_not_trusted(mock_workspace: Path, tmp_path: Path):
    """Old manifests (classification.class, no confirmation) become unconfirmed suggestions; old overrides stay final."""
    import json
    from src.catalog.manager import normalize_manifest
    catalog, sha = _saved_manifest(mock_workspace, tmp_path)
    m = catalog.get_manifest(sha)
    legacy = json.loads(json.dumps(m))
    legacy["classification"]["class"] = legacy["classification"].pop("suggested_class")
    del legacy["confirmation"]
    out = normalize_manifest(json.loads(json.dumps(legacy)))
    assert out["confirmation"]["status"] == "unconfirmed" and out["confirmation"]["final_class"] is None

    legacy["classification"]["class"] = "ResearchNote"
    legacy["human_override"] = {"active": True, "original_class": "AcademicPaper", "updated_by": "ashley",
                                "updated_at": "2026-11-01T00:00:00+00:00", "notes": "x"}
    out = normalize_manifest(legacy)
    assert out["confirmation"]["status"] == "overridden" and out["confirmation"]["final_class"] == "ResearchNote"
    assert out["classification"]["suggested_class"] == "AcademicPaper"


def test_staging_writes_human_records_and_edges_only_for_human_decisions(mock_workspace: Path, tmp_path: Path):
    import json
    catalog, sha = _saved_manifest(mock_workspace, tmp_path)
    staging = tmp_path / ".s3a" / "staging"
    bridge = S3ABridge(staging_dir=staging)

    counts = bridge.stage_ingestion(catalog)  # unconfirmed suggestion
    assert counts["human_lrs"] == 0 and counts["graph_edges"] == 0 and counts["ai_traces"] == 1
    paper = json.loads((staging / "academic_papers.jsonl").read_text().splitlines()[0])
    assert paper["warning_count"] == 1 and paper["open_access_flag"] == 0

    catalog.confirm(sha, "ashley")
    counts = bridge.stage_ingestion(catalog)
    assert counts["human_lrs"] == 1 and counts["graph_edges"] == 1
    paper = json.loads((staging / "academic_papers.jsonl").read_text().splitlines()[0])
    assert paper["warning_count"] == 0 and paper["open_access_flag"] == 1
