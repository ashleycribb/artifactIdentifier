"""S3A Harness Addon Bridge and Two-Stage Ingestion Pipeline (scholar_ingest_v1)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from src.catalog.manager import CatalogManager
from src.config import S3AConfig
from src.s3a.tile_ids import (
    TILE_AI_TRACE_LOG,
    TILE_HUMAN_LRS,
    VERB_ID_APPROVED,
    VERB_ID_OVERRODE,
)


def str_hash64(s: str) -> int:
    """Computes stable 64-bit integer hash from string using SHA-256."""
    h = hashlib.sha256(s.encode("utf-8")).digest()
    return struct.unpack("<Q", h[:8])[0]


def uuid_to_u64_pair(u_val: Any) -> Tuple[int, int]:
    """Converts a UUID object or string into (high, low) u64 pair."""
    if u_val is None:
        return (0, 0)
    if isinstance(u_val, str):
        try:
            u_obj = uuid.UUID(u_val)
        except Exception:
            return (str_hash64(u_val), 0)
    else:
        u_obj = u_val
    b = u_obj.bytes
    high = struct.unpack(">Q", b[:8])[0]
    low = struct.unpack(">Q", b[8:])[0]
    return (high, low)


class S3ABridge:
    """Interfaces with S3A Harness Addon and stages verified records into Hyper-Tiles 10-15."""

    def __init__(
        self,
        config: Optional[S3AConfig] = None,
        staging_dir: str | Path = ".s3a/staging",
    ):
        self.config = config or S3AConfig()
        self.staging_dir = Path(staging_dir).resolve()
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def preflight_check(self, workspace_path: str | Path) -> Tuple[bool, str]:
        """Supervisory gate: verifies workspace read permissions and staging environment readiness."""
        ws = Path(workspace_path)
        if not ws.exists() or not ws.is_dir():
            return False, f"Workspace path does not exist or is not a directory: {ws}"

        try:
            test_file = self.staging_dir / ".preflight_tmp"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
        except Exception as e:
            return False, f"Cannot write to staging directory: {e}"

        return True, "Preflight check passed: environment ready for autonomous scanning."

    def stage_ingestion(
        self,
        catalog_manager: CatalogManager,
        project_uuid: Optional[str] = None,
    ) -> Dict[str, int]:
        """Stage 1: Extracts verified manifests and writes NDJSON files according to scholar_ingest_v1."""
        manifests = catalog_manager.list_manifests()
        self.staging_dir.mkdir(parents=True, exist_ok=True)

        session_uuid = project_uuid or "d583943b-f5e6-5de5-9e24-2a82da40f8f6"
        high, low = uuid_to_u64_pair(session_uuid)

        papers_count = 0
        lrs_count = 0
        ai_traces_count = 0
        edges_count = 0

        papers_path = self.staging_dir / "academic_papers.jsonl"
        human_lrs_path = self.staging_dir / "human_lrs.jsonl"
        ai_traces_path = self.staging_dir / "ai_traces.jsonl"
        graph_edges_path = self.staging_dir / "graph_edges.jsonl"
        workspace_path = self.staging_dir / "workspace.json"

        with papers_path.open("w", encoding="utf-8") as f_papers, \
             human_lrs_path.open("w", encoding="utf-8") as f_lrs, \
             ai_traces_path.open("w", encoding="utf-8") as f_ai, \
             graph_edges_path.open("w", encoding="utf-8") as f_edges:

            for idx, m in enumerate(manifests):
                fp = m.get("fingerprint", {})
                cls_data = m.get("classification", {})
                decision = m.get("confirmation", {})
                human_decided = decision.get("status") in ("confirmed", "overridden")
                final_class = decision.get("final_class") if human_decided else None
                attrs = m.get("attributes", {})

                sha256 = fp.get("sha256", "")
                doi = attrs.get("doi")
                title = attrs.get("title") or Path(fp.get("file_path", "unknown")).name
                paper_id = str_hash64(doi if doi else sha256)
                year = 2024

                # Tile 12: AcademicPaperRecord
                paper_rec = {
                    "paper_id": paper_id,
                    "timestamp_sec": int(time.time()),
                    "hilbert_index": paper_id % (1 << 30),
                    "topic_x": float(paper_id % 1000),
                    "topic_y": float((paper_id >> 10) % 1000),
                    "topic_z": float(year),
                    "citation_count": 0,
                    "year": year,
                    # Class-derived fields use only the human's final class, never the agent's suggestion.
                    "venue_id": str_hash64(final_class or "Literature") % 100,
                    "open_access_flag": 1 if final_class == "AcademicPaper" else 0,
                    # Warn while no human has decided, or the final class is NeedsReview
                    "warning_count": 1 if (not human_decided or final_class == "NeedsReview") else 0,
                    "doi_prefix_hash": str_hash64(doi.split("/")[0] if doi and "/" in doi else "10.0000"),
                }
                f_papers.write(json.dumps(paper_rec) + "\n")
                papers_count += 1

                # Tile 10: HumanLrsRecord - written only for human decisions (confirm / override)
                if human_decided:
                    lrs_rec = {
                        "session_high": high,
                        "session_low": low,
                        "timestamp_sec": int(time.time()),
                        "actor_hash": str_hash64(decision.get("confirmed_by") or "researcher"),
                        "verb_id": VERB_ID_OVERRODE if decision["status"] == "overridden" else VERB_ID_APPROVED,
                        "decision_score": 1.0,
                        "object_hash": str_hash64(sha256),
                        "ai_tile": TILE_AI_TRACE_LOG,
                        "ai_record": idx,
                    }
                    f_lrs.write(json.dumps(lrs_rec) + "\n")
                    lrs_count += 1

                # Tile 11: AiTraceRecord - the agent's SUGGESTION trace, never a final decision
                ai_rec = {
                    "session_high": high,
                    "session_low": low,
                    "timestamp_sec": int(time.time()),
                    "agent_id": str_hash64("agent:scholar-classifier"),
                    "step_type": 1,  # classify
                    "confidence": float(cls_data.get("confidence", 0.9)),
                    "human_tile": TILE_HUMAN_LRS if human_decided else 0,
                    "human_record": lrs_count - 1 if human_decided else 0,
                    "hilbert_index": (high ^ low ^ paper_id) % (1 << 30),
                }
                f_ai.write(json.dumps(ai_rec) + "\n")
                ai_traces_count += 1

                # Tile 13: ResearchGraphEdgeRecord - classified_as edge only for a human-final class
                if final_class:
                    edge_rec = {
                        "subject_hash": str_hash64(sha256),
                        "object_hash": str_hash64(final_class),
                        "timestamp_sec": int(time.time()),
                        "hilbert_coord": (str_hash64(sha256) ^ str_hash64(final_class)) % (1 << 30),
                        "predicate_id": 1,  # classified_as
                        "weight": 1.0,
                    }
                    f_edges.write(json.dumps(edge_rec) + "\n")
                    edges_count += 1

        # Tile 14 / 15: Workspace metadata
        with workspace_path.open("w", encoding="utf-8") as f_ws:
            ws_data = {
                "project_high": high,
                "project_low": low,
                "question_hash": str_hash64("research_vault:classifier_intake"),
                "collection_mask": 1,
                "centroid_x": 0.0,
                "centroid_y": 0.0,
                "centroid_z": 2024.0,
                "status": 1,
            }
            json.dump(ws_data, f_ws, indent=2)

        return {
            "academic_papers": papers_count,
            "human_lrs": lrs_count,
            "ai_traces": ai_traces_count,
            "graph_edges": edges_count,
        }

    def commit_to_s3a(
        self,
        destination_s3a_path: Optional[str | Path] = None,
        fresh: bool = True,
        s3a_repo_path: Optional[str | Path] = None,
    ) -> Tuple[bool, str]:
        """Stage 2: Commits staged NDJSON records into native S3A archive using s3a-cli."""
        target_s3a = Path(destination_s3a_path or self.config.s3a_database_path).resolve()

        # Check if s3a repo path exists
        repo_setting = s3a_repo_path or self.config.s3a_repo_path or os.environ.get("S3A_REPO")
        repo = Path(repo_setting) if repo_setting else None

        if repo is not None and (repo / "Cargo.toml").exists() and shutil.which("cargo"):
            cmd = [
                "cargo",
                "run",
                "-q",
                "-p",
                "s3a-cli",
                "--",
                "scholar",
                "ingest",
                str(self.staging_dir),
                str(target_s3a),
            ]
            if fresh:
                cmd.append("--fresh")

            try:
                res = subprocess.run(
                    cmd,
                    cwd=str(repo),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode == 0:
                    return True, f"Successfully committed staged records to S3A archive: {target_s3a}\n{res.stdout}"
                else:
                    return False, f"s3a-cli ingestion failed with code {res.returncode}:\n{res.stderr}"
            except Exception as e:
                return False, f"Failed to execute s3a-cli: {e}"

        # Standalone mock commit: write simulation summary file
        target_s3a.parent.mkdir(parents=True, exist_ok=True)
        meta_info = {
            "status": "committed_stage2",
            "staging_dir": str(self.staging_dir),
            "target": str(target_s3a),
            "fresh": fresh,
            "timestamp": time.time(),
        }
        mock_meta = target_s3a.with_suffix(".s3a.simulated.json")
        mock_meta.write_text(json.dumps(meta_info, indent=2), encoding="utf-8")
        return True, f"Simulated S3A commit recorded: {mock_meta}"
