"""
Single source of truth for the S3A tile IDs used by this agent.

Canonical definitions live in the s3a-storage tile-type registry:
  https://github.com/ashleycribb/s3a-storage/blob/main/crates/s3a-core/src/registry.rs
  https://github.com/ashleycribb/s3a-storage/blob/main/crates/s3a-pack-scholar/src/pack.rs
The registry is Rust-only (no machine-readable export yet), so the values are
mirrored here. Do not hardcode tile numbers elsewhere; import from this module.
If s3a-storage changes its layout, update this file.
"""

TILE_HUMAN_LRS = 10        # HumanLrsRecord - human decisions only
TILE_AI_TRACE_LOG = 11     # AiTraceRecord - agent suggestions/traces
TILE_ACADEMIC_PAPERS = 12  # AcademicPaperRecord
TILE_RESEARCH_GRAPH = 13   # ResearchGraphEdgeRecord
TILE_SRS_WORKSPACE = 14    # SrsWorkspaceRecord
TILE_SRS_MANIFEST = 15     # SrsManifestHeader

# xAPI wire verb IDs used when staging human records (see s3a-pack-scholar/src/xapi.rs)
VERB_ID_APPROVED = 3       # used here for a human "confirmed"
VERB_ID_OVERRODE = 4       # NOTE: xapi.rs registers 4 as REJECTED; kept as-is for compatibility
