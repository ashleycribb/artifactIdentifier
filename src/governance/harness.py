"""Agent governance harness enforcing OWL job duties and xAPI job manual execution contracts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

PERMITTED_CAPABILITIES = {
    "scan_directory",
    "extract_metadata",
    "stage_manifest",
    "intake_srs",
    "export_srs",
    "preflight_check",
    "record_xapi",
    "ask_human",
}

FORBIDDEN_CAPABILITIES = {
    "physical_file_move",
    "physical_file_delete",
    "direct_binary_overwrite",
}

GATED_CAPABILITIES = {
    "commit_s3a",
}

AUTHORIZED_XAPI_VERBS = {
    "scanned": "http://adlnet.gov/expapi/verbs/scanned",
    "extracted": "https://w3id.org/xapi/s3a/verbs/extracted",
    "classified": "https://w3id.org/xapi/s3a/verbs/classified",
    "flagged_needs_review": "https://w3id.org/xapi/s3a/verbs/flagged_needs_review",
    "overrode": "https://w3id.org/xapi/s3a/verbs/overrode",
    "verified": "https://w3id.org/xapi/s3a/verbs/verified",
    "ingested": "https://w3id.org/xapi/s3a/verbs/ingested",
}


class GovernanceViolationError(Exception):
    """Raised when an agent attempts an action that violates OWL role duties or xAPI profile."""


class GovernanceHarness:
    """Enforces OWL role boundaries and records verifiable xAPI statements."""

    def __init__(
        self,
        agent_id: str = "scholar_classifier",
        role: str = "ClassifierAgent",
        audit_log_path: str | Path = ".s3a/audit_log.jsonl",
    ):
        self.agent_id = agent_id
        self.role = role
        self.audit_log_path = Path(audit_log_path)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def verify_action_permission(self, action_name: str) -> bool:
        """Verifies if an action is permitted under the agent's OWL Job Duties model."""
        clean_action = action_name.lower().replace("-", "_")

        if clean_action in FORBIDDEN_CAPABILITIES:
            raise GovernanceViolationError(
                f"Action '{action_name}' is strictly FORBIDDEN for role '{self.role}' "
                f"by OWL governance ontology. Agent is not permitted to mutate filesystem."
            )

        if clean_action in GATED_CAPABILITIES:
            raise GovernanceViolationError(
                f"Action '{action_name}' requires human supervisory gate approval before execution."
            )

        if clean_action not in PERMITTED_CAPABILITIES:
            raise GovernanceViolationError(
                f"Action '{action_name}' is not in the OWL Job Duties whitelist for role '{self.role}'."
            )

        return True

    def record_step(
        self,
        verb_key: str,
        object_id: str,
        object_type: str = "ResearchArtifact",
        context: Optional[Dict[str, Any]] = None,
        actor_name: Optional[str] = None,
        is_human: bool = False,
    ) -> Dict[str, Any]:
        """Validates and records an immutable xAPI 1.0.3 statement adhering to the Job Manual profile."""
        if verb_key not in AUTHORIZED_XAPI_VERBS:
            raise GovernanceViolationError(
                f"Verb '{verb_key}' is not authorized under S3A Scholar xAPI profile."
            )

        statement_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        actor = {
            "name": actor_name or ("Researcher" if is_human else self.agent_id),
            "account": {
                "homePage": "https://s3a.storage",
                "name": actor_name or ("human_supervisor" if is_human else f"agent_{self.agent_id}"),
            },
        }

        verb = {
            "id": AUTHORIZED_XAPI_VERBS[verb_key],
            "display": {"en": verb_key},
        }

        activity = {
            "id": object_id,
            "definition": {
                "type": f"https://w3id.org/xapi/s3a/activity/{object_type.lower()}",
                "name": {"en": Path(object_id).name if "/" in object_id or "\\" in object_id else object_id},
            },
        }

        statement = {
            "id": statement_id,
            "timestamp": timestamp,
            "actor": actor,
            "verb": verb,
            "object": activity,
            "context": {
                "contextActivities": {
                    "category": [
                        {
                            "id": "https://w3id.org/xapi/s3a-scholar/v1",
                            "definition": {"type": "http://adlnet.gov/expapi/activities/profile"},
                        }
                    ]
                },
                "extensions": context or {},
            },
        }

        # Append to audit log
        with self.audit_log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(statement, ensure_ascii=False) + "\n")

        return statement
