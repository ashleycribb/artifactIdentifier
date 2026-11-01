# Implementation Readiness Report (Stage 9)

**Target:** `docs/designs/research_artifact_classifier.md` (`DetailedRange`: lines 356–548)  
**Reviewers:** Tech Lead Implementation Reviewer (`egm-implementation-readiness`), Codebase Details Reviewer (`egm-codebase-details`), Implementation Style Reviewer (`egm-style`)  
**Standard:** `resources/document_standards/implementation-readiness-standard.md`

---

## Executive Summary
While the conceptual classification pipeline and taxonomic structure are clear, the Detailed Implementation Plan and Verification Plan are **not yet ready for coding**. An implementing engineer is blocked by critical omissions:
1. Missing text extraction module and missing format parsing dependencies (`python-docx`, TeX/Markdown extractors).
2. Missing project packaging configuration (`pyproject.toml` / console script registration).
3. Completely unspecified database, vector storage, and embedding models for the S3A bridge layer.
4. Missing LLM SDK dependencies, configuration schemas, and structured output mechanics.
5. Incomplete test suite breakdown that excludes core modules and fixtures.

---

## Consolidated Findings

### 🔴 Blockers

#### 1. Missing Document Text Extractor Module & Incomplete Multi-Format Parsers
* **Reviewers**: `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope**: Target Files (lines 369–488), Dependencies (line 519)
* **Critique & Flaw**:
  The architecture diagram depicts a `Parser["Document Text & Heading Parser"]` (line 110), and downstream contracts require raw text: `extract_identifiers(text: str)`, `match_author_identity(doc_text: str)`, and `classify_with_schema(text_snippet: str)`. However, the implementation plan completely omits any document text extractor module (e.g., `src/extractors/text.py`).
  Furthermore, while `.docx` is claimed as a supported format (lines 11, 21, 75, 103, 174, 361, 433), `python-docx` is missing from dependencies. No parsing strategy is defined for `.tex` or `.md` files.
* **Required Remediation**: Add `src/extractors/text.py` declaring `extract_document_text(file_path: Path, max_tokens: int = 2048) -> ExtractedTextResult`, covering PDF (`pypdf`), PPTX (`python-pptx`), DOCX (`python-docx`), LaTeX, and Markdown. Add `python-docx` to dependencies.

#### 2. Unspecified Persistence Engines, Vector Models & Missing DB Dependencies in S3A Bridge
* **Reviewers**: `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope**: `src/s3a/bridge.py` (lines 471–476), `src/config.py` (line 403), Dependencies (line 519)
* **Critique & Flaw**:
  `src/s3a/bridge.py` promises to insert into an S3A relational schema, write RDF triples to a triplestore, and update a RAG vector index. However:
  - No database engine, ORM, DDL, or table schemas are specified.
  - No triplestore target (disk-persisted Turtle/XML file vs SPARQL endpoint) is defined.
  - No vector store or embedding model is named.
  - Line 519 lists zero database drivers, zero vector database packages, and zero embedding libraries.
* **Required Remediation**: Explicitly standardize on an embedded local storage model (e.g., SQLite via `sqlite3` for relational metadata, local serialized RDF via `rdflib`, and a lightweight local vector store) or decouple the RAG indexing to downstream platform services. Add concrete drivers to dependencies.

#### 3. Undefined LLM Provider, SDK, and Missing Dependencies
* **Reviewers**: `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope**: `src/classifier/llm_client.py` (lines 444–449), `src/config.py` (lines 397–404), Dependencies (line 519)
* **Critique & Flaw**:
  `src/classifier/llm_client.py` defines `classify_with_schema` enforcing JSON Schema output. However:
  - No LLM SDK or HTTP client (`openai`, `google-genai`, `anthropic`, `httpx`) is specified or included in dependencies.
  - `src/config.py` lacks fields for API keys, base URLs, model names, timeout, and retry settings.
  - No tokenizer library (e.g., `tiktoken`) is specified to enforce the 2,048 token budget prior to network calls.
* **Required Remediation**: Designate the concrete LLM SDK, add `LLMConfig` to `src/config.py`, and add the SDK and tokenizer to dependencies.

---

### 🟡 Major Issues

#### 4. Omission of Project Packaging Manifest (`pyproject.toml`)
* **Reviewer**: `egm-codebase-details`
* **Affected Scope**: Target Files list (lines 369–512), Verification Plan (line 519)
* **Critique & Flaw**:
  The Verification Plan mandates `pip install -e .` and CLI invocation via `s3a-agent` (lines 482–487, 519). However, neither `pyproject.toml` nor `setup.py` exists in the repository or in the file creation list. Without declaring packaging configuration and `[project.scripts] s3a-agent = "src.cli:main"`, installation and CLI invocation fail immediately.
* **Required Remediation**: Add `pyproject.toml` to the file list, specifying build system, dependencies, and console script entrypoints.

#### 5. Undefined DSL Grammar for `taxonomy_registry.yaml` Rules
* **Reviewer**: `egm-implementation-readiness`
* **Affected Scope**: `schemas/taxonomy_registry.yaml` (lines 380–386), `src/classifier/engine.py` (lines 435–443)
* **Critique & Flaw**:
  Line 385 states entries declare `rules (required extensions, geometry bounds, author matching requirements)`. The plan leaves the evaluation grammar and boolean logic (all-match vs any-match) undefined.
* **Required Remediation**: Document the concrete YAML rule grammar with a full example entry for each baseline class.

#### 6. Schema Inconsistency Regarding Sidecar `attributes` Block
* **Reviewer**: `egm-implementation-readiness`
* **Affected Scope**: `schemas/artifact_tag.v1.json` (lines 371–379) vs. Architecture Sidecar Example (lines 215–221)
* **Critique & Flaw**:
  The architectural example includes a dedicated `attributes` block (`title`, `authors`, `doi`, `page_count`, `dimensions`), but the JSON Schema structural contract in line 374 completely omits `attributes` from its declared schema fields.
* **Required Remediation**: Update line 378 to declare the JSON schema definition for `attributes`.

#### 7. Incomplete Test Suite Breakdown and Coverage Gaps
* **Reviewers**: `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope**: `tests/` (lines 489–508), Verification Plan (lines 521–532)
* **Critique & Flaw**:
  The plan lists only 5 test files, leaving `bibliographic.py`, `author_matcher.py`, `llm_client.py`, `xapi.py`, `bridge.py`, and `cli.py` without tests. Line 531 restricts 90% branch coverage strictly to extractors, classifier, and sidecar, exempting provenance, S3A bridge, and CLI. Furthermore, no shared test fixture harness (`tests/conftest.py`) or mock LLM client is documented.
* **Required Remediation**: Add `tests/conftest.py` with mock LLM/document fixtures, add test coverage for remaining modules, and apply 90% branch coverage across all `src/` modules.

#### 8. Sidecar Naming Collision and State Tracking for In-Place Edits
* **Reviewers**: `egm-codebase-details`, `egm-implementation-readiness`
* **Affected Scope**: `src/sidecar/manager.py` (lines 450–457), `src/sidecar/validator.py` (lines 458–464)
* **Critique & Flaw**:
  Line 452 describes `<filename>.s3a.json`, whereas lines 192 and 273 specify `document.ext.s3a.json`. Truncating extensions causes filename collisions when multiple files share a stem (`manuscript.pdf`, `manuscript.docx`, `manuscript.tex`). Additionally, `detect_human_override` expects a `previous_state` dictionary without explaining where it is persisted across CLI runs.
* **Required Remediation**: Standardize naming on `<filename>.<ext>.s3a.json`. Clarify whether previous state is stored directly inside the sidecar or via a local staging manifest.

#### 9. Hyperbolic and Unsubstantiated Claims in Detailed Plan
* **Reviewer**: `egm-style`
* **Affected Scope**: Lines 445–446, 466–467
* **Critique & Flaw**:
  Phrases like "eliminating ungrounded hallucinations" and "Produces immutable IEEE/xAPI audit events" are technically inaccurate (JSON schema restricts syntax, not hallucinations; local file append is not immutable).
* **Required Remediation**: Replace with precise descriptions: "enforces JSON Schema output constraints" and "Produces standardized audit event records".

---

### 🟢 Nits

#### 10. Missing OWL Reasoner Dependency in Verification Plan
* **Reviewer**: `egm-codebase-details`
* **Affected Scope**: Lines 505–507, 519
* **Critique & Flaw**:
  `test_ontology_compliance.py` claims to test for zero disjointness violations, but base `rdflib` lacks an OWL 2 DL reasoner.
* **Required Remediation**: Add `owlrl` or `pyshacl` to dependencies if OWL reasoning is executed.

#### 11. Hardcoded Classification Threshold vs. `ScannerConfig`
* **Reviewer**: `egm-codebase-details`
* **Affected Scope**: Line 441 vs. Line 402
* **Critique & Flaw**:
  The `0.85` confidence threshold is hardcoded in `engine.py` rather than exposed as a configurable parameter on `ScannerConfig`.

#### 12. Self-Referential Commentary and Inconsistent Test Wording
* **Reviewer**: `egm-style`
* **Affected Scope**: Lines 358, 417 vs 495, 541, 547–548
* **Critique & Flaw**:
  Meta-commentary in line 358, discrepancy between poster threshold in extractor (>= 24 in) and test (> 24x36 in), and process watermarks in the footer.
