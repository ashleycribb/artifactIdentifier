"""Centralized metadata catalog manager for .s3a/metadata/<sha256>.json."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.catalog.validator import validate_human_override, validate_manifest_schema
from src.fingerprint import atomic_write_json, compute_sha256, read_json


class CatalogManager:
    """Manages workspace research artifact manifests and human overrides."""

    def __init__(self, metadata_dir: str | Path = ".s3a/metadata"):
        self.metadata_dir = Path(metadata_dir).resolve()
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def get_manifest_path(self, sha256: str) -> Path:
        return self.metadata_dir / f"{sha256}.json"

    def save_manifest(self, manifest: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validates and saves a manifest to .s3a/metadata/<sha256>.json."""
        valid, err = validate_manifest_schema(manifest)
        if not valid:
            return False, err

        sha256 = manifest["fingerprint"]["sha256"]
        target_path = self.get_manifest_path(sha256)
        try:
            atomic_write_json(target_path, manifest)
            return True, None
        except Exception as e:
            return False, f"Failed to write manifest: {e}"

    def get_manifest(self, sha256: str) -> Optional[Dict[str, Any]]:
        path = self.get_manifest_path(sha256)
        if path.is_file():
            try:
                return read_json(path)
            except Exception:
                return None
        return None

    def list_manifests(self) -> List[Dict[str, Any]]:
        manifests = []
        for p in self.metadata_dir.glob("*.json"):
            try:
                data = read_json(p)
                if isinstance(data, dict) and "fingerprint" in data:
                    manifests.append(data)
            except Exception:
                continue
        return manifests

    def apply_override(
        self,
        sha256: str,
        new_class: str,
        user_name: str,
        notes: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Applies a human override to a manifest, preserving the original class."""
        manifest = self.get_manifest(sha256)
        if not manifest:
            return False, f"Manifest with sha256 '{sha256}' not found"

        current_class = manifest["classification"]["class"]
        now_iso = datetime.now(timezone.utc).isoformat()

        # Update human override block
        manifest["human_override"] = {
            "active": True,
            "original_class": current_class,
            "updated_by": user_name,
            "updated_at": now_iso,
            "notes": notes or f"Manually overridden by {user_name}",
        }

        # Update classification block
        manifest["classification"]["class"] = new_class
        manifest["classification"]["confidence"] = 1.0
        manifest["classification"]["source"] = "human_override"
        manifest["classification"]["rationale"] = f"Authoritative human override asserted by {user_name}"

        # Validate override rules
        val_ok, val_err = validate_human_override(manifest)
        if not val_ok:
            return False, val_err

        return self.save_manifest(manifest)

    def check_integrity(self) -> Dict[str, Any]:
        """Checks workspace integrity, detecting modified files, missing files, and overrides."""
        all_manifests = self.list_manifests()
        valid = []
        stale = []
        missing = []
        overridden = []

        for m in all_manifests:
            fp = m.get("fingerprint", {})
            file_path_str = fp.get("file_path")
            recorded_hash = fp.get("sha256")

            if not file_path_str:
                continue

            file_path = Path(file_path_str)
            if not file_path.exists():
                missing.append(m)
                continue

            # Verify hash
            try:
                current_hash = compute_sha256(file_path)
                if current_hash != recorded_hash:
                    stale.append({"manifest": m, "current_hash": current_hash})
                else:
                    valid.append(m)
            except Exception:
                missing.append(m)

            if m.get("human_override", {}).get("active"):
                overridden.append(m)

        return {
            "total_manifests": len(all_manifests),
            "valid_count": len(valid),
            "stale_count": len(stale),
            "missing_count": len(missing),
            "overridden_count": len(overridden),
            "stale_files": stale,
            "missing_files": missing,
        }
