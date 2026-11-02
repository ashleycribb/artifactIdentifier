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
        verb_key="suggested",
        object_id="document.pdf",
        context={"suggested_class": "AcademicPaper", "confidence": 0.95},
    )

    assert stmt["verb"]["display"]["en"] == "suggested"
    assert audit_file.exists()
    assert "suggested" in audit_file.read_text(encoding="utf-8")

    # Invalid verb rejection
    with pytest.raises(GovernanceViolationError, match="not authorized"):
        harness.record_step(verb_key="deleted_file", object_id="document.pdf")


@pytest.mark.parametrize("verb", ["classified", "confirmed", "overrode"])
def test_final_verbs_refuse_non_human_actor(tmp_path: Path, verb: str):
    audit_file = tmp_path / "audit.jsonl"
    harness = GovernanceHarness(audit_log_path=audit_file)

    # Agent (default) actor is refused
    with pytest.raises(GovernanceViolationError, match="requires a human actor"):
        harness.record_step(verb_key=verb, object_id="document.pdf")
    # A human flag attributed to the agent itself is refused too
    with pytest.raises(GovernanceViolationError, match="cannot be attributed to the agent"):
        harness.record_step(verb_key=verb, object_id="document.pdf", actor_name="scholar_classifier", is_human=True)
    assert not audit_file.exists() or audit_file.read_text(encoding="utf-8") == ""

    # A named human is accepted
    stmt = harness.record_step(verb_key=verb, object_id="document.pdf", actor_name="ashley", is_human=True)
    assert stmt["verb"]["display"]["en"] == verb


def test_suggested_and_confirmed_verbs_in_xapi_profile():
    import json
    profile = json.loads((Path(__file__).resolve().parent.parent / "schemas" / "xapi_agent_profile.json").read_text(encoding="utf-8"))
    labels = {c["prefLabel"]["en"] for c in profile["concepts"] if c["type"] == "Verb"}
    assert {"suggested", "confirmed"} <= labels
