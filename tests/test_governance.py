"""Tests for OWL role duties and xAPI job manual execution contracts."""

from pathlib import Path
import pytest
from src.governance.harness import GovernanceHarness, GovernanceViolationError


def test_owl_job_duties_permissions(tmp_path: Path):
    harness = GovernanceHarness(audit_log_path=tmp_path / "audit.jsonl")

    # Allowed capabilities
    assert harness.verify_action_permission("scan_directory") is True
    assert harness.verify_action_permission("extract_metadata") is True
    assert harness.verify_action_permission("preflight_check") is True

    # Forbidden destructive actions
    with pytest.raises(GovernanceViolationError, match="strictly FORBIDDEN"):
        harness.verify_action_permission("physical_file_move")

    with pytest.raises(GovernanceViolationError, match="strictly FORBIDDEN"):
        harness.verify_action_permission("physical_file_delete")

    # Gated actions
    with pytest.raises(GovernanceViolationError, match="requires human supervisory gate"):
        harness.verify_action_permission("commit_s3a")


def test_xapi_job_manual_recording(tmp_path: Path):
    audit_file = tmp_path / "audit.jsonl"
    harness = GovernanceHarness(audit_log_path=audit_file)

    stmt = harness.record_step(
        verb_key="classified",
        object_id="document.pdf",
        context={"class": "AcademicPaper", "confidence": 0.95},
    )

    assert stmt["verb"]["display"]["en"] == "classified"
    assert audit_file.exists()
    assert "classified" in audit_file.read_text(encoding="utf-8")

    # Invalid verb rejection
    with pytest.raises(GovernanceViolationError, match="not authorized"):
        harness.record_step(verb_key="deleted_file", object_id="document.pdf")
