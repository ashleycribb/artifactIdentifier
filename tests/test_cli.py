"""Integration tests for s3a-agent CLI subcommands."""

from pathlib import Path
from click.testing import CliRunner
from src.cli import main


def test_cli_scan_status_and_verify(mock_workspace: Path, monkeypatch, tmp_path: Path):
    runner = CliRunner()
    meta_dir = tmp_path / ".s3a" / "metadata"
    staging_dir = tmp_path / ".s3a" / "staging"
    audit_file = tmp_path / ".s3a" / "audit_log.jsonl"

    # Patch working directory / config locations
    monkeypatch.chdir(tmp_path)

    # 1. Test scan command
    scan_result = runner.invoke(main, ["scan", str(mock_workspace), "--author", "Ashley Smith"])
    assert scan_result.exit_code == 0
    assert "Scan complete" in scan_result.output

    # 2. Test status command
    status_result = runner.invoke(main, ["status"])
    assert status_result.exit_code == 0
    assert "Total Manifests" in status_result.output

    # 3. Test verify command
    verify_result = runner.invoke(main, ["verify"])
    assert verify_result.exit_code == 0
    assert "verified" in verify_result.output.lower()

    # 4. Test ingest command
    ingest_result = runner.invoke(main, ["ingest", "--fresh"])
    assert ingest_result.exit_code == 0
    assert "[Stage 1] Staging manifests" in ingest_result.output


def test_cli_scan_suggests_and_confirm_finalizes(mock_workspace: Path, monkeypatch, tmp_path: Path):
    import json
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    scan = runner.invoke(main, ["scan", str(mock_workspace)])
    assert scan.exit_code == 0
    assert "suggested:" in scan.output and "suggested (not final)" in scan.output

    audit = (tmp_path / ".s3a" / "audit_log.jsonl").read_text(encoding="utf-8")
    verbs = [json.loads(line)["verb"]["display"]["en"] for line in audit.splitlines()]
    assert "suggested" in verbs and "classified" not in verbs  # the agent never records 'classified'

    manifests = [json.loads(p.read_text()) for p in (tmp_path / ".s3a" / "metadata").glob("*.json")]
    assert manifests and all(m["confirmation"]["status"] == "unconfirmed" for m in manifests)
    target = next(m for m in manifests if m["classification"]["suggested_class"] == "AcademicPaper")
    sha = target["fingerprint"]["sha256"]

    status = runner.invoke(main, ["status"])
    assert "Awaiting Human" in status.output and "(suggested)" in status.output

    # The agent identity cannot confirm
    refused = runner.invoke(main, ["confirm", sha, "--user", "scholar_classifier"])
    assert refused.exit_code == 1 and "Refused" in refused.output

    ok = runner.invoke(main, ["confirm", sha, "--user", "ashley", "--notes", "checked DOI"])
    assert ok.exit_code == 0, ok.output
    saved = json.loads((tmp_path / ".s3a" / "metadata" / f"{sha}.json").read_text())
    assert saved["confirmation"]["status"] == "confirmed"
    assert saved["confirmation"]["final_class"] == "AcademicPaper"
    audit = (tmp_path / ".s3a" / "audit_log.jsonl").read_text(encoding="utf-8")
    assert '"confirmed"' in audit

    # Re-scan preserves the human decision
    rescan = runner.invoke(main, ["scan", str(mock_workspace)])
    assert "CONFIRMED" in rescan.output

    missing = runner.invoke(main, ["confirm", "0" * 64, "--user", "ashley"])
    assert missing.exit_code == 1
