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
