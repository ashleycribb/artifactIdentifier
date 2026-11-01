# Comprehension Test Report

**Target:** `docs/designs/research_artifact_classifier.md` (`FeatureRange: 1..355`, `DetailedRange: 356..548`)  
**Reviewer:** Naive Reader (Comprehension Goldfish)  
**Standard:** Plain Comprehension / Self-Containment Audit  
**Inspected Context:** Target design document and `arXiv-2607.02514v1.tar.gz`.

---

## Paraphrase

### What this proposes
This document proposes an automated, local-first research artifact classification and staging agent that scans unorganized academic file collections containing multiple formats (`.pdf`, `.docx`, `.pptx`, `.tex`, `.md`, `.txt`). The system deterministically computes cryptographic SHA-256 fingerprints, inspects layout geometry, extracts bibliographic identifiers (DOIs, arXiv IDs), and correlates local author identities before falling back to a schema-constrained LLM for ambiguous items. Scanned artifacts are paired with transparent, human-editable JSON sidecars (`.s3a.json`), audited through IEEE/xAPI lifecycle statements, validated against an OWL 2 DL ontology, and staged for user verification prior to ingestion into the S3A research database, knowledge graph, and RAG index.

### How the existing system works, per this document
Per this document, researchers currently maintain heterogeneous research files scattered across local folders and cloud storage with inconsistent naming conventions and no standardized taxonomy. Existing automated classification tools rely on ungrounded, end-to-end LLM passes or automated sorting scripts that frequently confuse author drafts with published literature, hallucinate semantic tags, bury metadata in opaque vector stores or binary headers, or break build paths by moving files without verification. Outside of stating that the target "S3A system" contains a research database, a knowledge graph/DAG indexer, and a RAG vector index, the document does not describe how S3A currently operates, how artifacts are ingested today, or what existing services comprise the S3A platform.

---

## Audit Findings

### 1. Missing Text Extraction Module and Missing `.docx` Dependency
* **Severity**: 🔴 Blocker
* **Affected Scope**: Technical Plan (Layer 1 Parser, lines 110, 140), Detailed Implementation Plan (Target Files, lines 369–488), Verification Plan (line 519).
* **Discrepancy Description & Rationale**:
  * The architecture diagram depicts a `Parser["Document Text & Heading Parser"]` (line 110) feeding the deterministic rules and LLM client, and downstream modules (`extract_identifiers`, `check_publication_headers`, `match_author_identity`, `classify_with_schema`) explicitly require extracted text inputs (`text: str`, `doc_text: str`, `text_snippet: str`).
  * However, in the detailed Target Files breakdown (lines 369–488), there is no module or class defined for document text extraction from `.pdf`, `.docx`, `.tex`, or `.md` files.
  * Furthermore, while `.docx` is listed as a supported artifact format throughout the document (lines 11, 21, 75, 103, 174, 361, 433), the dependency manifest in line 519 lists only `pypdf, python-pptx, pydantic, pyyaml, rdflib, pytest, jsonschema`. It omits any Word processing library (such as `python-docx`). A developer implementing this plan has no specification or library for extracting text and headers from `.docx` or `.tex` files.

### 2. Undefined Core System Acronym and Missing Architecture Specification for "S3A"
* **Severity**: 🟡 Major
* **Affected Scope**: Title (line 1), Overview (line 13), Technical Plan (lines 98, 132–136), Target Files (`src/config.py` line 403, `src/s3a/bridge.py` lines 471–476).
* **Discrepancy Description & Rationale**:
  * The entire project is centered around the "S3A research database", "S3A Ingestion Agent", and "S3A System / Harness", yet "S3A" is never expanded or defined anywhere in the document.
  * The document assumes existing infrastructure (a relational database, triplestore/graph engine, and RAG vector index), but provides no connection protocol, API endpoints, schema specifications, or engine definitions (e.g., PostgreSQL, SQLite, Neo4j, GraphDB). A new team member cannot determine whether S3A is a local SQLite database, a microservice, or an external cloud platform.

### 3. Missing Vector Embedding and Vector Database Dependencies for RAG Indexing
* **Severity**: 🟡 Major
* **Affected Scope**: Architecture (lines 135, 164), Component Breakdown (line 287), Target Files (`src/s3a/bridge.py`, lines 473–475), Dependencies (line 519).
* **Discrepancy Description & Rationale**:
  * The document specifies that `src/s3a/bridge.py` indexes clean text chunks tagged with ontological metadata into a "RAG / Vector Index" (lines 287, 475).
  * However, no embedding model, text-chunking library, or vector store client (e.g., Chroma, FAISS, Qdrant) is specified in `src/config.py` or included in the dependency list (line 519). The mechanism by which the bridge generates embeddings and commits them to the vector index is completely unstated.

### 4. Ambiguous Ingestion Behavior: Physical Relocation vs. Pure Metadata Indexing
* **Severity**: 🟡 Major
* **Affected Scope**: Goals (line 50), Open Questions (line 67), CUJ 4 (line 90), Target Files (`src/s3a/bridge.py`, lines 471–476, `src/cli.py`, line 486).
* **Discrepancy Description & Rationale**:
  * Goal line 50 mentions "dry-run relocation manifests, requiring explicit user approval before physical file movement or S3A ingestion," and CUJ 4 (line 90) states the user reviews "proposed S3A destinations."
  * Conversely, line 67 lists physical relocation vs. content-addressed virtual indexing as an unresolved Open Question, while Alternative D (line 336) states that decoupling metadata tagging from physical file relocation protects project integrity. In addition, the implementation contract for `src/s3a/bridge.py` (line 475) only describes writing records to relational tables, RDF graphs, and vector indexes without moving files.
  * It is unclear whether running `s3a-agent ingest` moves/copies raw files to an archive directory or only registers paths in the database.

### 5. Vague Mechanism for Detecting Human Sidecar Overrides on Disk
* **Severity**: 🟡 Major
* **Affected Scope**: Section 3 (lines 208–226), Section 5 (lines 364, 460–464).
* **Discrepancy Description & Rationale**:
  * Line 225 states that if a user edits `"class": "GrantProposal"` in a text editor, the system detects this edit as verified ground truth. In line 463, `detect_human_override(sidecar_path: Path, previous_state: dict)` requires a `previous_state` dictionary to detect changes.
  * However, the document does not explain where `previous_state` is retrieved from during a standalone CLI execution (`s3a-agent verify` or `s3a-agent status`). If the user modifies `paper.pdf.s3a.json` directly on disk and leaves `"active": false` under `human_override`, the system cannot know whether the file was manually modified or generated by an older rule pass without maintaining a separate persistence cache or running a full diff.

### 6. Unspecified LLM Provider, Model Configuration, and Credentials
* **Severity**: 🟡 Major
* **Affected Scope**: Section 2 (lines 186–189), Security & Privacy (line 343), Target Files (`src/config.py`, lines 400–404; `src/classifier/llm_client.py`, lines 444–449).
* **Discrepancy Description & Rationale**:
  * The fallback classification engine invokes an LLM when rule confidence is below 0.85. However, `src/config.py` omits all configuration attributes for the model provider (e.g., OpenAI, Anthropic, Gemini, or a local Ollama instance), endpoint URLs, and API key management.
  * Furthermore, while line 343 states that files are never transmitted to external APIs unless LLM fallback is explicitly authorized, the document does not specify where or how this user authorization flag is configured.

### 7. Undefined Institutional Acronyms and Jargon (`EGM`, `LRS`)
* **Severity**: 🟢 Nit
* **Affected Scope**: Open Questions (line 68), Target Files (`src/config.py` line 403, `src/provenance/xapi.py` line 469), Footer (lines 547–548).
* **Discrepancy Description & Rationale**:
  * Lines 547–548 state "Generated via EGM design drafting process" without defining what EGM stands for.
  * Lines 68, 403, and 469 reference dispatching xAPI statements to an "LRS" or "HTTP LRS endpoint" without defining the acronym (Learning Record Store) or specifying the expected authentication scheme (Basic Auth, Bearer Token, OAuth2).

### 8. Unstated Storage Location and Initialization of `user_profile.json`
* **Severity**: 🟢 Nit
* **Affected Scope**: Technical Plan (line 177), Target Files (`src/config.py` line 401, `src/extractors/author_matcher.py` line 432).
* **Discrepancy Description & Rationale**:
  * Author matching relies on comparing document author blocks against a `user_profile.json` file. The document does not define the default path for this file (e.g., `~/.config/s3a/user_profile.json` vs. workspace root), nor does it provide a CLI command or template to initialize it.

### 9. Unclear Quantification of Deterministic Fast-Path Confidence Scores
* **Severity**: 🟢 Nit
* **Affected Scope**: Component Breakdown (line 204), Target Files (`src/classifier/engine.py`, lines 440–442).
* **Discrepancy Description & Rationale**:
  * Line 441 specifies that an LLM fallback is triggered if fast-path confidence is < 0.85, and line 204 shows a sample output confidence of `0.94` from a `deterministic_rule`. However, the document does not define how non-binary confidence scores (such as 0.94) are calculated by deterministic heuristics.
