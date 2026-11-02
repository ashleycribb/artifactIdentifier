"""Centralized metadata catalog manager for .s3a/metadata/<sha256>.json."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.catalog.validator import validate_human_override, validate_manifest_schema
from src.fingerprint import atomic_write_json, compute_sha256, read_json


def normalize_manifest(data: Dict[str, Any]) -> Dict[str, Any]:
    """Upgrade a legacy manifest (classification.class, no confirmation block) in memory.

    Legacy manifests treated the agent's class as final. Under the human-judgment
    model only an active human override counts as final; everything else becomes
    an unconfirmed suggestion.
    """
    cls = data.get("classification")
    if not isinstance(cls, dict) or "class" not in cls:
        return data
    legacy_class = cls.pop("class")
    override = data.get("human_override") or {}
    if override.get("active"):
        cls["suggested_class"] = override.get("original_class") or legacy_class
        cls["source"] = "deterministic_rule" if cls.get("source") == "human_override" else cls.get("source")
        data["confirmation"] = {
            "status": "overridden",
            "final_class": legacy_class,
            "confirmed_by": override.get("updated_by"),
            "confirmed_at": override.get("updated_at"),
            "notes": override.get("notes"),
        }
    else:
        cls["suggested_class"] = legacy_class
        data["confirmation"] = {
            "status": "unconfirmed",
            "final_class": None,
            "confirmed_by": None,
            "confirmed_at": None,
            "notes": None,
        }
    return data


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
                return normalize_manifest(read_json(path))
            except Exception:
                return None
        return None

    def list_manifests(self) -> List[Dict[str, Any]]:
        manifests = []
        for p in self.metadata_dir.glob("*.json"):
            try:
                data = normalize_manifest(read_json(p))
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

        # The agent's suggestion is preserved untouched; the human decision is recorded separately.
        suggested_class = manifest["classification"]["suggested_class"]
        now_iso = datetime.now(timezone.utc).isoformat()

        manifest["human_override"] = {
            "active": True,
            "original_class": suggested_class,
            "updated_by": user_name,
            "updated_at": now_iso,
            "notes": notes or f"Manually overridden by {user_name}",
        }
        manifest["confirmation"] = {
            "status": "overridden",
            "final_class": new_class,
            "confirmed_by": user_name,
            "confirmed_at": now_iso,
            "notes": notes or f"Manually overridden by {user_name}",
        }

        # Validate override rules
        val_ok, val_err = validate_human_override(manifest)
        if not val_ok:
            return False, val_err

        return self.save_manifest(manifest)

    def confirm(
        self,
        sha256: str,
        user_name: str,
        notes: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Human accepts the agent's suggested class as final."""
        manifest = self.get_manifest(sha256)
        if not manifest:
            return False, f"Manifest with sha256 '{sha256}' not found"
        if not user_name or not user_name.strip():
            return False, "Confirmation requires a human 'user' identity"

        suggested = manifest["classification"]["suggested_class"]
        if suggested == "NeedsReview":
            return False, "Suggestion is 'NeedsReview' (the agent could not decide); use 'override' to assign a class"

        manifest["confirmation"] = {
            "status": "confirmed",
            "final_class": suggested,
            "confirmed_by": user_name,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
            "notes": notes or f"Suggestion confirmed by {user_name}",
        }
        return self.save_manifest(manifest)

    def check_integrity(self) -> Dict[str, Any]:
        """Checks workspace integrity, detecting modified files, missing files, and overrides."""
        all_manifests = self.list_manifests()
        valid = []
        stale = []
        missing = []
        overridden = []
        confirmed = []
        unconfirmed = []

        for m in all_manifests:
            fp = m.get("fingerprint", {})
            file_path_str = fp.get("file_path")
            recorded_hash = fp.get("sha256")

            status = m.get("confirmation", {}).get("status", "unconfirmed")
            if status == "unconfirmed":
                unconfirmed.append(m)
            elif status == "confirmed":
                confirmed.append(m)

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
            "confirmed_count": len(confirmed),
            "unconfirmed_count": len(unconfirmed),
            "stale_files": stale,
            "missing_files": missing,
        }
