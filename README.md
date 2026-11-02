# S3A Research Artifact Classifier & Ingestion Agent

An autonomous research artifact classification and virtual ingestion system built natively for **S3A Storage** (`s3a-storage`). The system inspects heterogeneous workspaces containing literature, notes, manuscripts, slide decks, posters, and compound submission packages (`.tar.gz`), categorizing them into native S3A Capsule and Compound Tiles without third-party databases (no SQLite, DuckDB, or Postgres).

---

## Key Capabilities

1. **Deterministic Multi-Format Inspection**:
   - Classifies academic papers, author drafts, research notes, conference posters, slide decks, and `.tar.gz` source bundles.
   - Extracts DOIs, arXiv IDs, Dublin Core, and Highwire Press metadata tags (`<meta name="citation_title">`).
   - Automatically binds child figure sub-assets (`figures/*.pdf`, `images/`) to their parent manuscripts, eliminating standalone false positives.
   - Decouples author identity from draft status: past published papers by the local author are correctly classified as `AcademicPaper` rather than `AuthorDraft`.

2. **The agent suggests, the human decides**:
   - The classifier writes `classification.suggested_class` plus a `confidence` score. That is a suggestion, not a decision.
   - A class is final only after a human runs `s3a-agent confirm <sha256>` or `s3a-agent override <sha256> <class>`; the decision is stored in the manifest's `confirmation` block and only then do human LRS records and `classified_as` graph edges get staged.
   - An artifact the agent could not decide (`NeedsReview`) can only be overridden, not confirmed.

3. **Dual-Plane Agent Governance**:
   - **OWL 2 DL "Job Duties" Model** (`ontology/s3a_agent_governance.owl`): Formally defines agent role permissions, prohibiting physical file modifications and destructive file movements.
   - **xAPI "Job Manual" Runtime Contract** (`schemas/xapi_agent_profile.json`): Intercepts all agent actions, validating against authorized verbs (`scanned`, `extracted`, `suggested`, `confirmed`, `classified`, `flagged_needs_review`, `overrode`, `verified`, `ingested`). The agent can only record `suggested`; `confirmed`, `classified` and `overrode` are refused unless the actor is a human and logging immutable audit statements to `.s3a/audit_log.jsonl`.

4. **Zero-Database Native S3A Storage Integration**:
   - Tile IDs live in one module, `src/s3a/tile_ids.py`, mirroring the [s3a-storage tile-type registry](https://github.com/ashleycribb/s3a-storage/blob/main/crates/s3a-pack-scholar/src/pack.rs). Maps records directly to S3A Hyper-Tiles 10–15 (`s3a-pack-scholar` / `ADDON_EDU`):
     - **Tile 10 (`HumanLrsRecord`)**: Human feedback, overrides, and xAPI statements.
     - **Tile 11 (`AiTraceRecord`)**: Classification steps and anti-hallucination traces.
     - **Tile 12 (`AcademicPaperRecord`)**: Literature corpus, DOIs, and 3D Hilbert coordinates.
     - **Tile 13 (`ResearchGraphEdgeRecord`)**: Knowledge graph relations and OWL axioms.
     - **Tile 14 (`SrsWorkspaceRecord`)**: Active workspace context and collection bounds.
     - **Tile 15 (`SrsManifestHeader`)**: Snapshot container manifest with hardware CRC32C checksums (`SCHOLAR_LAYOUT_VERSION_V1 = 1`).

5. **S3A Native Template Agent**:
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
s3a-agent scan /path/to/research/vault --author "<your name>"
```

To enable the privacy-gated LLM fallback for ambiguous files:
```bash
s3a-agent scan /path/to/research/vault --allow-remote-llm
```

Each file gets a *suggested* class. Nothing is final yet.

### 1b. Confirm a Suggestion (human decision)
```bash
s3a-agent confirm <sha256> --user "<your name>" --notes "checked DOI"
```

### 2. Check Catalog Status
Displays suggestions awaiting a human, confirmations, overrides, counts by class (suggested classes are marked `(suggested)`), and filesystem integrity:

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

## Repository Notes

- `.s3a/` (manifests, staging, audit log, local config) is gitignored; never commit it.
- Earlier design-review reports live in `docs/reviews/`.
- Native ingest uses a local s3a-storage checkout from `s3a.s3a_repo_path` in `.s3a/config.json` or env `S3A_REPO`; without it the commit is simulated.

## Testing

Run the automated test suite with coverage:

```bash
pytest tests/ -v --cov=src
```
