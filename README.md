# S3A Research Artifact Classifier & Ingestion Agent

An autonomous research artifact classification and virtual ingestion system built natively for **S3A Storage** (`s3a-storage`). The system inspects heterogeneous workspaces containing literature, notes, manuscripts, slide decks, posters, and compound submission packages (`.tar.gz`), categorizing them into native S3A Capsule and Compound Tiles without third-party databases (no SQLite, DuckDB, or Postgres).

---

## Key Capabilities

1. **Deterministic Multi-Format Inspection**:
   - Classifies academic papers, author drafts, research notes, conference posters, slide decks, and `.tar.gz` source bundles.
   - Extracts DOIs, arXiv IDs, Dublin Core, and Highwire Press metadata tags (`<meta name="citation_title">`).
   - Automatically binds child figure sub-assets (`figures/*.pdf`, `images/`) to their parent manuscripts, eliminating standalone false positives.
   - Decouples author identity from draft status: past published papers by the local author are correctly classified as `AcademicPaper` rather than `AuthorDraft`.

2. **Dual-Plane Agent Governance**:
   - **OWL 2 DL "Job Duties" Model** (`ontology/s3a_agent_governance.owl`): Formally defines agent role permissions, prohibiting physical file modifications and destructive file movements.
   - **xAPI "Job Manual" Runtime Contract** (`schemas/xapi_agent_profile.json`): Intercepts all agent actions, validating against authorized verbs (`scanned`, `extracted`, `classified`, `flagged_needs_review`, `overrode`, `verified`, `ingested`) and logging immutable audit statements to `.s3a/audit_log.jsonl`.

3. **Zero-Database Native S3A Storage Integration**:
   - Maps records directly to S3A Hyper-Tiles 10–15 (`s3a-pack-scholar` / `ADDON_EDU`):
     - **Tile 10 (`HumanLrsRecord`)**: Human feedback, overrides, and xAPI statements.
     - **Tile 11 (`AiTraceRecord`)**: Classification steps and anti-hallucination traces.
     - **Tile 12 (`AcademicPaperRecord`)**: Literature corpus, DOIs, and 3D Hilbert coordinates.
     - **Tile 13 (`ResearchGraphEdgeRecord`)**: Knowledge graph relations and OWL axioms.
     - **Tile 14 (`SrsWorkspaceRecord`)**: Active workspace context and collection bounds.
     - **Tile 15 (`SrsManifestHeader`)**: Snapshot container manifest with hardware CRC32C checksums (`SCHOLAR_LAYOUT_VERSION_V1 = 1`).

4. **S3A Native Template Agent**:
   - Packaged as [`agents/scholar_classifier.toml`](./agents/scholar_classifier.toml) modeled directly on `s3a-storage/agents/scholar_reviewer.toml`, enabling `s3a-harness` to validate thresholds, execute preflight checks, and enforce MCP tool whitelists.

---

## Installation

Install using `uv` or `pip`:

```bash
uv pip install -e .
# Or with dev dependencies:
uv pip install -e ".[dev]"
```

---

## CLI Usage

### 1. Scan a Research Workspace
Recursively scans files, computes cryptographic SHA-256 fingerprints, executes fast-path taxonomy rules, and generates manifests in `.s3a/metadata/<sha256>.json`:

```bash
s3a-agent scan /path/to/research/vault --author "Dr. Ashley Smith"
```

To enable the privacy-gated LLM fallback for ambiguous files:
```bash
s3a-agent scan /path/to/research/vault --allow-remote-llm
```

### 2. Check Catalog Status
Displays total counts by classification class, active human overrides, and filesystem integrity:

```bash
s3a-agent status
```

### 3. Assert an Authoritative Human Override
Overrides an agent classification while preserving the original label and logging researcher attribution:

```bash
s3a-agent override <sha256> AuthorDraft --user "ashley" --notes "Active working manuscript"
```

### 4. Verify Catalog Cryptographic Integrity
Validates JSON schemas and checks that documents have not been modified or deleted on disk:

```bash
s3a-agent verify
```

### 5. Ingest into S3A Storage
Executes Stage 1 staging (`scholar_ingest_v1` NDJSON) and Stage 2 native ingestion into binary `.s3a` archives:

```bash
s3a-agent ingest --out research_vault.s3a --fresh
```

---

## Testing

Run the automated test suite with coverage:

```bash
pytest tests/ -v --cov=src
```
