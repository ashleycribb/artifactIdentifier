"""CLI interface for s3a-agent."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Optional
import click

from src.catalog.manager import CatalogManager
from src.classifier.engine import CANDIDATE_CLASSES, ClassificationEngine
from src.config import AppConfig
from src.governance.harness import GovernanceHarness, GovernanceViolationError
from src.s3a.bridge import S3ABridge


@click.group()
@click.version_option(version="0.1.0")
def main():
    """S3A Research Artifact Classifier & Autonomous Governance Agent."""
    pass


@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--allow-remote-llm", is_flag=True, default=False, help="Permit cloud LLM fallback for ambiguous files")
@click.option("--author", multiple=True, help="Registered researcher names for author disambiguation")
def scan(directory: str, allow_remote_llm: bool, author: tuple):
    """Scan workspace, inspect artifacts, and generate centralized .s3a/metadata/ manifests."""
    config = AppConfig.load()
    if allow_remote_llm:
        config.llm.allow_remote = True
    if author:
        config.user_profile.author_names = list(author)

    workspace_path = Path(directory).resolve()
    harness = GovernanceHarness()
    bridge = S3ABridge(config.s3a)

    # 1. Preflight supervisory check
    ok, msg = bridge.preflight_check(workspace_path)
    if not ok:
        click.secho(f"Preflight Check Failed: {msg}", fg="red")
        sys.exit(1)

    click.secho(f"Starting scan on workspace: {workspace_path}", fg="cyan")
    harness.record_step("scanned", str(workspace_path), object_type="Workspace")

    engine = ClassificationEngine(config)
    catalog = CatalogManager(config.scanner.metadata_dir)

    scanned_count = 0
    classified_count = 0
    excluded_sub_assets = 0

    # Scan files recursively
    for p in workspace_path.rglob("*"):
        if not p.is_file():
            continue
        # Skip internal .s3a metadata directory
        if ".s3a" in p.parts:
            continue

        scanned_count += 1
        manifest = engine.classify_file(p, workspace_root=workspace_path)
        if manifest is None:
            excluded_sub_assets += 1
            continue

        sha256 = manifest["fingerprint"]["sha256"]
        cls_name = manifest["classification"]["suggested_class"]
        conf = manifest["classification"]["confidence"]

        # Preserve any existing human decision (confirm or override)
        existing = catalog.get_manifest(sha256)
        if existing and existing.get("confirmation", {}).get("status") in ("confirmed", "overridden"):
            conf_block = existing["confirmation"]
            click.echo(f"  [{conf_block['status'].upper()}] {p.name} -> {conf_block['final_class']} (Preserved human decision)")
            continue

        saved_ok, err = catalog.save_manifest(manifest)
        if not saved_ok:
            click.secho(f"  [ERROR] {p.name}: {err}", fg="red")
            continue

        classified_count += 1
        # The agent only suggests; a human makes it final with `s3a-agent confirm` / `override`.
        verb = "flagged_needs_review" if cls_name == "NeedsReview" else "suggested"
        harness.record_step(
            verb,
            str(p),
            context={"sha256": sha256, "suggested_class": cls_name, "confidence": conf},
        )

        color = "yellow" if cls_name == "NeedsReview" else "green"
        click.secho(f"  [suggested: {cls_name} ({conf:.2f})] {p.name}", fg=color)

    click.echo("-" * 60)
    click.secho(
        f"Scan complete: {scanned_count} files discovered, "
        f"{classified_count} suggested (not final), {excluded_sub_assets} sub-assets excluded.",
        fg="bright_green",
    )
    click.echo("Review suggestions, then run: s3a-agent confirm <sha256>  (or: s3a-agent override <sha256> <class>)")


@main.command()
def status():
    """Display catalog summary, override counts, and health status."""
    config = AppConfig.load()
    catalog = CatalogManager(config.scanner.metadata_dir)
    integrity = catalog.check_integrity()
    manifests = catalog.list_manifests()

    click.secho("=== S3A Research Artifact Catalog Status ===", fg="cyan", bold=True)
    click.echo(f"Metadata Directory:  {catalog.metadata_dir}")
    click.echo(f"Total Manifests:     {integrity['total_manifests']}")
    click.echo(f"Valid Files:         {integrity['valid_count']}")
    click.echo(f"Stale Files:         {integrity['stale_count']}")
    click.echo(f"Missing Files:       {integrity['missing_count']}")
    click.echo(f"Awaiting Human:      {integrity['unconfirmed_count']} (suggestions not yet confirmed)")
    click.echo(f"Human Confirmed:     {integrity['confirmed_count']}")
    click.echo(f"Human Overrides:     {integrity['overridden_count']}")

    # Count by class: final (human-decided) class if present, else the agent's suggestion
    counts = {}
    for m in manifests:
        conf_block = m.get("confirmation", {})
        if conf_block.get("final_class"):
            key = conf_block["final_class"]
        else:
            key = f"{m.get('classification', {}).get('suggested_class', 'Unknown')} (suggested)"
        counts[key] = counts.get(key, 0) + 1

    click.echo("\nArtifact Breakdown by Class:")
    for c, cnt in sorted(counts.items()):
        click.echo(f"  - {c:<24}: {cnt}")

    if integrity["stale_count"] > 0:
        click.secho(f"\nWarning: {integrity['stale_count']} files modified since last scan. Run 's3a-agent scan' to refresh.", fg="yellow")


@main.command()
@click.argument("sha256")
@click.option("--user", default="researcher", help="Researcher username or ORCID confirming the suggestion")
@click.option("--notes", default=None, help="Audit rationale for confirmation")
def confirm(sha256: str, user: str, notes: Optional[str]):
    """Confirm the agent's suggested class as final (human decision)."""
    config = AppConfig.load()
    catalog = CatalogManager(config.scanner.metadata_dir)
    harness = GovernanceHarness()

    manifest = catalog.get_manifest(sha256)
    if not manifest:
        click.secho(f"Confirm Failed: Manifest with sha256 '{sha256}' not found", fg="red")
        sys.exit(1)
    suggested = manifest["classification"]["suggested_class"]

    try:
        harness.require_human_actor("confirmed", True, user)
    except GovernanceViolationError as e:
        click.secho(f"Confirm Refused: {e}", fg="red")
        sys.exit(1)

    ok, err = catalog.confirm(sha256, user, notes)
    if not ok:
        click.secho(f"Confirm Failed: {err}", fg="red")
        sys.exit(1)

    harness.record_step(
        "confirmed",
        sha256,
        context={"final_class": suggested, "user": user, "notes": notes},
        actor_name=user,
        is_human=True,
    )
    click.secho(f"Confirmed: {sha256} -> {suggested} (by {user})", fg="green")


@main.command()
@click.argument("sha256")
@click.argument("new_class", type=click.Choice(CANDIDATE_CLASSES))
@click.option("--user", default="researcher", help="Researcher username or ORCID asserting override")
@click.option("--notes", default="Human researcher manual override", help="Audit rationale for override")
def override(sha256: str, new_class: str, user: str, notes: str):
    """Assert an authoritative human override on an artifact classification."""
    config = AppConfig.load()
    catalog = CatalogManager(config.scanner.metadata_dir)
    harness = GovernanceHarness()

    ok, err = catalog.apply_override(sha256, new_class, user, notes)
    if not ok:
        click.secho(f"Override Failed: {err}", fg="red")
        sys.exit(1)

    harness.record_step(
        "overrode",
        sha256,
        context={"new_class": new_class, "user": user, "notes": notes},
        actor_name=user,
        is_human=True,
    )
    click.secho(f"Successfully asserted override: {sha256} -> {new_class} (by {user})", fg="green")


@main.command()
def verify():
    """Verify integrity of manifests, schema compliance, and document hashes."""
    config = AppConfig.load()
    catalog = CatalogManager(config.scanner.metadata_dir)
    integrity = catalog.check_integrity()

    click.secho("Verifying catalog integrity...", fg="cyan")
    if integrity["stale_count"] == 0 and integrity["missing_count"] == 0:
        click.secho(f"All {integrity['valid_count']} manifests are intact and cryptographically verified.", fg="green")
    else:
        click.secho(
            f"Integrity check completed with issues: "
            f"{integrity['stale_count']} stale, {integrity['missing_count']} missing.",
            fg="yellow",
        )


@main.command()
@click.option("--out", default=None, help="Destination S3A database file path")
@click.option("--fresh", is_flag=True, default=True, help="Create destination archive from scratch")
def ingest(out: Optional[str], fresh: bool):
    """Stage manifests into scholar_ingest_v1 NDJSON and commit to native S3A storage."""
    config = AppConfig.load()
    catalog = CatalogManager(config.scanner.metadata_dir)
    bridge = S3ABridge(config.s3a, staging_dir=config.scanner.staging_dir)
    harness = GovernanceHarness()

    click.secho("[Stage 1] Staging manifests into scholar_ingest_v1 format...", fg="cyan")
    counts = bridge.stage_ingestion(catalog)
    click.echo(
        f"  Staged: {counts['academic_papers']} papers, {counts['human_lrs']} human records, "
        f"{counts['ai_traces']} AI traces, {counts['graph_edges']} graph edges."
    )

    click.secho("[Stage 2] Committing staged records to S3A storage archive...", fg="cyan")
    harness.verify_action_permission("preflight_check")
    ok, msg = bridge.commit_to_s3a(destination_s3a_path=out, fresh=fresh)
    if ok:
        harness.record_step("ingested", out or config.s3a.s3a_database_path, object_type="S3ADatabase")
        click.secho(msg, fg="green")
    else:
        click.secho(msg, fg="red")
        sys.exit(1)


if __name__ == "__main__":
    main()
