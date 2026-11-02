"""Manifest schema validation and human override integrity verifier."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import jsonschema

VALID_CLASSES = {
    "AcademicPaper",
    "AuthorDraft",
    "ResearchNote",
    "ConferencePoster",
    "ConferencePresentation",
    "SourcePackage",
    "NeedsReview",
}


def load_manifest_schema() -> Dict[str, Any]:
    """Loads the canonical JSON schema for artifact manifests."""
    schema_path = Path(__file__).resolve().parent.parent.parent / "schemas" / "artifact_manifest.v1.json"
    if schema_path.is_file():
        with schema_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def validate_manifest_schema(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validates a manifest against JSON Schema."""
    schema = load_manifest_schema()
    if not schema:
        # If schema file not found, perform baseline structural checks
        if "fingerprint" in data and "classification" in data and "human_override" in data:
            return True, None
        return False, "Missing required top-level manifest sections"

    try:
        jsonschema.validate(instance=data, schema=schema)
        return True, None
    except jsonschema.ValidationError as e:
        return False, f"JSON Schema validation error: {e.message} at path: {list(e.path)}"
    except Exception as e:
        return False, f"Schema validation failed: {e}"


def validate_human_override(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Checks whether a human override is syntactically and semantically valid."""
    override = data.get("human_override")
    if not override or not isinstance(override, dict):
        return False, "Missing or invalid 'human_override' block"

    is_active = override.get("active", False)
    if not is_active:
        return True, None

    target_class = data.get("confirmation", {}).get("final_class")
    if target_class not in VALID_CLASSES:
        return False, f"Target overridden class '{target_class}' is not in valid taxonomy classes: {VALID_CLASSES}"

    if not override.get("updated_by"):
        return False, "Human override requires 'updated_by' identity"

    if not override.get("updated_at"):
        return False, "Human override requires 'updated_at' timestamp"

    return True, None
