# Consolidated EGM Review Report

**Target Document:** [`docs/designs/research_artifact_classifier.md`](file:///c:/Users/Ashley/Downloads/artifactIdentifier/docs/designs/research_artifact_classifier.md)  
**Evaluated Context:** `C:\Users\Ashley\Downloads\arXiv-2607.02514v1.tar.gz` (arXiv submission tarball with LaTeX sources, figures, macros, bib, and emerging web/HTML preprint formats).  
**Review Preset:** Uninterrupted Full Flow (Stages 5, 6, 7, 8, 9)  
**Date:** 2026-11-01  

---

## 1. Executive Summary

The autonomous Goldfish review swarm has evaluated [`docs/designs/research_artifact_classifier.md`](file:///c:/Users/Ashley/Downloads/artifactIdentifier/docs/designs/research_artifact_classifier.md) across all five review phases. 

The panel affirms that the document addresses a genuine researcher pain point: identifying and categorizing mixed research files without breaking local build environments or corrupting downstream knowledge structures. However, across all reviewer lenses, the design exhibits three systemic flaws that prevent it from being viable for immediate implementation:

1. **Enterprise Abstraction Creep & YAGNI Violations**: The design forces an enterprise Semantic Web stack (W3C OWL 2 DL description logic reasoning, RDF triplestores, and `rdflib` dependencies) and an e-learning training specification (IEEE xAPI targeting Learning Record Stores) onto what should be a lean, local-first filesystem classifier.
2. **Real-World Academic Artifact Blindspots**: The specification models research files as isolated, flat PDFs and Word docs. Real academic workspaces (such as the inspected `arXiv-2607.02514v1.tar.gz` bundle) rely on compressed source archives (`.tar.gz`, `.zip`) containing LaTeX sources, macros, and embedded figure PDFs (`figures/*.pdf`), as well as modern responsive HTML/MathML preprints. The current scanner will either ignore archives or misclassify sub-asset figure plots as independent posters and slides while littering sidecars inside LaTeX build trees.
3. **Critical Implementation Gaps**: An engineer cannot build the proposed system because foundational components are missing: there is no document text extractor module (`src/extractors/text.py`), no `.docx` parsing library, no project packaging manifest (`pyproject.toml`), no LLM SDK/configuration models, and no concrete database engine or vector storage schemas for the S3A bridge.

---

## 2. Reviewer Status Matrix

| Stage | Phase | Reviewer Subagent | Status | Total Findings |
| :--- | :--- | :--- | :--- | :--- |
| **Stage 5** | Initial Zoom Out | Skeptical Architect (`egm-zoom-out`) | **Complete** | 2 Blockers, 4 Majors, 1 Nit |
| **Stage 6** | Comprehension Test | Naive Reader (`egm-comprehension`) | **Complete** | 1 Blocker, 5 Majors, 3 Nits |
| **Stage 7** | Critic Review | Design Critic (`egm-design`) | **Complete** | 2 Blockers, 4 Majors, 2 Nits |
| **Stage 7** | Critic Review | Structural Goldfish (`egm-structural`) | **Complete** | 1 Major, 2 Nits |
| **Stage 7** | Critic Review | Technical Style (`egm-style`) | **Complete** | 3 Majors, 3 Nits |
| **Stage 8** | Intermediate Zoom Out | Skeptical Architect (`egm-zoom-out`) | **Complete** | 3 Blockers, 2 Majors, 1 Nit |
| **Stage 9** | Implementation Readiness | Tech Lead (`egm-implementation-readiness`) | **Complete** | 3 Blockers, 4 Majors, 1 Nit |
| **Stage 9** | Implementation Readiness | Codebase Details (`egm-codebase-details`) | **Complete** | 1 Blocker, 5 Majors, 1 Nit |
| **Stage 9** | Implementation Readiness | Implementation Style (`egm-style`) | **Complete** | 2 Majors, 5 Nits |

---

## 3. Consolidated Action Items by Priority

### 🔴 Critical Blockers

#### [ACT-BLK-01] Strip Enterprise OWL DL and xAPI Stack in Favor of Lean Schemas
* **Source Stages**: Stage 5 (Findings 1 & 2), Stage 8 (Finding 3)
* **Problem**: Mandating an OWL 2 DL ontology (`s3a_research_ontology.owl`), description logic disjointness axioms, RDF triplestores, and an e-learning xAPI LRS event dispatcher adds massive complexity, heavy dependencies (`rdflib`), and runtime failure points for a local file classification tool.
* **Action Required**: Unless formal OWL DL reasoning and xAPI LRS compliance are strictly external system requirements inherited from the broader S3A platform, replace OWL 2 DL with a standard Pydantic/JSON Schema (`schemas/taxonomy.json`) and replace xAPI with a standard, local append-only JSONL audit log (`.s3a/audit_log.jsonl`).

#### [ACT-BLK-02] Define Document Text Extraction Module & Multi-Format Parsing Contracts
* **Source Stages**: Stage 6 (Finding 1), Stage 9 (Readiness Finding 1, Details Finding 1)
* **Problem**: Downstream modules (`extract_identifiers`, `match_author_identity`, `classify_with_schema`) require raw text and headers, but no text extraction module is defined in the file breakdown or architecture. Furthermore, `.docx` is listed as supported, but `python-docx` is missing from dependencies, and no extraction strategy exists for `.tex` or `.md`.
* **Action Required**: Add `src/extractors/text.py` declaring `extract_document_text(file_path: Path, max_tokens: int = 2048) -> ExtractedTextResult`. Add `python-docx` to dependencies and define parsing strategies for LaTeX preambles and Markdown frontmatter.

#### [ACT-BLK-03] Account for Compound Archives (`.tar.gz`/`.zip`) and Sub-Asset Figure Filtering
* **Source Stages**: Stage 5 (Finding 3), Stage 7 (Finding 1), Stage 8 (Finding 4)
* **Problem**: Real-world preprints (like `arXiv-2607.02514v1.tar.gz`) are compound packages containing LaTeX sources, macros, and embedded figure PDFs (`figures/*.pdf`). The scanner cannot ingest archives and risks classifying individual figure plots as standalone posters or presentations, littering sidecars inside source trees.
* **Action Required**: Add `.tar.gz` and `.zip` as recognized container types (`SourceArchive` / `PreprintBundle`). Apply directory exclusion heuristics so that auxiliary folders (`figures/`, `images/`, `macros/`) sharing a parent manuscript are bound to the parent document rather than classified as standalone top-level artifacts.

#### [ACT-BLK-04] Define Packaging Manifest (`pyproject.toml`) and Concrete LLM Client Contracts
* **Source Stages**: Stage 6 (Finding 6), Stage 9 (Readiness Findings 2 & 3, Details Findings 2 & 4)
* **Problem**: The plan commands `pip install -e .` and CLI usage `s3a-agent`, but lacks `pyproject.toml` or console script definitions. The fallback classifier specifies structured JSON Schema LLM calls, but names no LLM SDK, includes no LLM configuration model (`LLMConfig`), and omits tokenizer libraries.
* **Action Required**: Add `pyproject.toml` with `[project.scripts] s3a-agent = "src.cli:main"`. Add an explicit LLM SDK (`openai>=1.0` or `google-genai`), add `LLMConfig` to `src/config.py`, and add a tokenizer (e.g. `tiktoken`) to dependencies.

#### [ACT-BLK-05] Resolve Sidecar Storage Strategy: Centralize Workspace Metadata in `.s3a/`
* **Source Stages**: Stage 5 (Finding 6), Stage 7 (Finding 2), Stage 8 (Finding 5)
* **Problem**: Writing adjacent `<filename>.<ext>.s3a.json` sidecars next to every file doubles file counts, pollutes Git working trees, triggers cloud sync thrashing, leaves orphan files upon deletion, and contradicts Section "Open Questions" which listed storage strategy as unresolved.
* **Action Required**: Resolve the open question: default to a central workspace metadata store at `<workspace>/.s3a/metadata/<sha256>.json` (or an indexed local SQLite catalog), keeping user project directories clean. If adjacent sidecars are supported, make them an explicit opt-in with automated `.gitignore` management.

#### [ACT-BLK-06] Reject "Fix Creep": Avoid Local SLMs and In-Scanner RAG Vector Engines
* **Source Stages**: Stage 8 (Findings 1 & 2)
* **Problem**: Remediating privacy and RAG gaps by embedding local Small Language Models (ONNX, PyTorch, llama-cpp) and full vector databases (Chroma, FAISS) into a filesystem scanner balloons the binary footprint and operational complexity.
* **Action Required**: Excise vector embedding and RAG indexing from this tool; leave vector search to downstream S3A platform consumers. For ambiguous documents where deterministic rules fail, simply assign a status of `NeedsReview` / `Unclassified` locally rather than deploying heavy on-device neural networks.

---

### 🟡 Major Action Items

#### [ACT-MAJ-01] Support Modern Scholarly HTML Preprints & Web Bundles
* **Source Stages**: Stage 5 (Finding 3), Stage 7 (Finding 3)
* **Action Required**: Add `.html` / `.htm` to supported extensions. Implement a Scholarly HTML extractor that parses Highwire Press (`<meta name="citation_title">`), Dublin Core, and DOM-embedded DOIs/arXiv links.

#### [ACT-MAJ-02] Robust Author Disambiguation & Self-Citation False-Positive Guards
* **Source Stages**: Stage 5 (Finding 5), Stage 7 (Finding 4)
* **Action Required**: Use ORCID and institutional domain matching rather than naive surname substring matching. Differentiate *Authorship* from *Status* (draft vs. published copy) so a researcher downloading their own past published paper is not mislabeled as an active draft. Enforce minimum page counts ($\ge 3$) for presentations to eliminate single-slide figure false positives.

#### [ACT-MAJ-03] Enforce Architectural Privacy Gate & LLM Token Budgeting
* **Source Stages**: Stage 7 (Findings 5 & 6)
* **Action Required**: Eliminate silent transmission of unreleased documents to external APIs. Require an explicit user confirmation flag (`--allow-remote-llm`) to trigger cloud LLM inference. Implement batching and global token spend caps.

#### [ACT-MAJ-04] Reconcile Sidecar `attributes` Block in JSON Schema Contract
* **Source Stages**: Stage 9 (Readiness Finding 6)
* **Action Required**: Update `schemas/artifact_tag.v1.json` to formally declare the `attributes` block (`title`, `authors`, `doi`, `page_count`, `dimensions`) matching Section 3.

#### [ACT-MAJ-05] Document Concrete DSL Grammar for `taxonomy_registry.yaml` Rules
* **Source Stages**: Stage 9 (Readiness Finding 5)
* **Action Required**: Formalize the rule evaluation grammar in `schemas/taxonomy_registry.yaml` with concrete boolean schemas (`extensions`, `geometry_bounds`, `author_match_mode`) and provide complete YAML examples for all baseline classes.

#### [ACT-MAJ-06] Expand Unit Test Infrastructure and Mock Harness
* **Source Stages**: Stage 9 (Readiness Finding 7, Details Finding 5)
* **Action Required**: Add `tests/conftest.py` with mock LLM responses and document fixtures. Add dedicated test files for bibliographic extraction, author matching, and CLI commands. Apply the 90% branch coverage requirement across all `src/` modules.

#### [ACT-MAJ-07] Add Mandatory Blueprint Section: `## Risks & Mitigations`
* **Source Stages**: Stage 7 (Structural Finding 1)
* **Action Required**: Add a dedicated `## Risks & Mitigations` section mapping failure modes (token exhaustion, malformed sidecars, hashing bottlenecks, network failures) to concrete architectural mitigations.

#### [ACT-MAJ-08] Define "S3A" Acronym and Clarify Relocation vs. Virtual Ingestion
* **Source Stages**: Stage 6 (Findings 2 & 4)
* **Action Required**: Expand "S3A" upon first use. Resolve the open question on file movement: state explicitly that ingestion is 100% virtual indexing and content-addressed registration; original files are never physically relocated.

#### [ACT-MAJ-09] Standardize Sidecar Naming & Implement Human Override State Tracking
* **Source Stages**: Stage 6 (Finding 5), Stage 9 (Readiness Finding 8, Details Finding 6)
* **Action Required**: Standardize file naming on `<filename>.<ext>.s3a.json` to prevent collisions. Clarify that `detect_human_override` reads `human_override.original_class` directly from the sidecar JSON itself rather than relying on an ephemeral memory dictionary.

---

### 🟢 Nits & Style Polish

* **[ACT-NIT-01] Eliminate Promotional Modifiers**: Replace overused promotional terms ("transparent", "accurately", "total auditability", "zero silent drift") with dry technical descriptions ("plain-text JSON", "heuristic classification", "audit logging"). (Stage 7 Style Findings 2 & 3).
* **[ACT-NIT-02] Terminology Precision (Fingerprint vs. Manifest)**: Change "human-editable metadata fingerprints" to "human-editable metadata manifests containing an immutable content fingerprint". (Stage 7 Style Finding 1).
* **[ACT-NIT-03] Replace Slang and Informal Phrasing**: Replace "black-box vector stores", "on the fly", "context window dumps", and "bonded to files" with formal technical prose. (Stage 7 Style Finding 4).
* **[ACT-NIT-04] Correct Hyperbolic Claims**: Replace "eliminating ungrounded hallucinations" and "Produces immutable xAPI events" with precise claims. (Stage 9 Style Findings 1 & 2).
* **[ACT-NIT-05] Heading and List Symmetry**: Unify problem definitions under `## Problem Statement` and standardize bullet formatting in `## Goals`. (Stage 7 Structural Findings 2 & 3).
* **[ACT-NIT-06] Reconcile Poster Thresholds**: Align extractor threshold (`>= 24 in / 610mm`) with test suite descriptions. (Stage 9 Style Finding 4).
* **[ACT-NIT-07] Expose Confidence Threshold in `ScannerConfig`**: Move the hardcoded `0.85` threshold out of `engine.py` and into `ScannerConfig`. (Stage 9 Details Finding 7).
* **[ACT-NIT-08] Add Debounce and Atomic Writes**: Add a 30-second debounce on filesystem modification listeners and enforce atomic file writes (write-to-temp and rename). (Stage 7 Design Findings 7 & 8).
* **[ACT-NIT-09] Remove Process Watermarks**: Remove `*Drafted with EGM*` and metadata comments from the final technical specification. (Stage 9 Style Finding 7).

---

## 4. Cross-Stage Traceability Matrix

| Raw Finding Reference | Source Report | Reviewer Lens | Consolidated Action Item |
| :--- | :--- | :--- | :--- |
| **Finding 1: Formal OWL 2 DL Stack** | `zoom_out_report.md` | `egm-zoom-out` | **[ACT-BLK-01]** |
| **Finding 2: xAPI LRS Integration** | `zoom_out_report.md` | `egm-zoom-out` | **[ACT-BLK-01]** |
| **Finding 3: Archive Bundles & HTML** | `zoom_out_report.md` | `egm-zoom-out` | **[ACT-BLK-03]**, **[ACT-MAJ-01]** |
| **Finding 4: Multi-DB Sprawl** | `zoom_out_report.md` | `egm-zoom-out` | **[ACT-BLK-01]**, **[ACT-BLK-06]** |
| **Finding 5: Fragile Draft Heuristic** | `zoom_out_report.md` | `egm-zoom-out` | **[ACT-MAJ-02]** |
| **Finding 6: Sidecar Clutter** | `zoom_out_report.md` | `egm-zoom-out` | **[ACT-BLK-05]** |
| **Finding 7: Module Fragmentation** | `zoom_out_report.md` | `egm-zoom-out` | **[ACT-BLK-01]** |
| **Finding 1: Missing Text Extractor** | `comprehension_report.md` | `egm-comprehension` | **[ACT-BLK-02]** |
| **Finding 2: Undefined S3A Acronym** | `comprehension_report.md` | `egm-comprehension` | **[ACT-MAJ-08]** |
| **Finding 3: Missing Vector DB/Models** | `comprehension_report.md` | `egm-comprehension` | **[ACT-BLK-06]** |
| **Finding 4: Relocation vs Indexing** | `comprehension_report.md` | `egm-comprehension` | **[ACT-MAJ-08]** |
| **Finding 5: Override Detection State** | `comprehension_report.md` | `egm-comprehension` | **[ACT-MAJ-09]** |
| **Finding 6: Unspecified LLM Config** | `comprehension_report.md` | `egm-comprehension` | **[ACT-BLK-04]** |
| **Finding 7: Undefined Acronyms** | `comprehension_report.md` | `egm-comprehension` | **[ACT-MAJ-08]** |
| **Finding 8: Unstated Profile Path** | `comprehension_report.md` | `egm-comprehension` | **[ACT-NIT-05]** |
| **Finding 9: Fast-Path Confidence** | `comprehension_report.md` | `egm-comprehension` | **[ACT-NIT-07]** |
| **Finding 1: Compound Archives** | `critic_report.md` | `egm-design` | **[ACT-BLK-03]** |
| **Finding 2: Workspace Sidecar Sprawl** | `critic_report.md` | `egm-design` | **[ACT-BLK-05]** |
| **Finding 3: HTML Papers** | `critic_report.md` | `egm-design` | **[ACT-MAJ-01]** |
| **Finding 4: Author Disambiguation** | `critic_report.md` | `egm-design` | **[ACT-MAJ-02]** |
| **Finding 5: Unbounded Token Costs** | `critic_report.md` | `egm-design` | **[ACT-MAJ-03]** |
| **Finding 6: Privacy Breach** | `critic_report.md` | `egm-design` | **[ACT-MAJ-03]** |
| **Finding 7: Missing Risks Section** | `critic_report.md` | `egm-structural` | **[ACT-MAJ-07]** |
| **Finding 8: Fingerprint vs Manifest** | `critic_report.md` | `egm-style` | **[ACT-NIT-02]** |
| **Finding 9: Buzzword Repetition** | `critic_report.md` | `egm-style` | **[ACT-NIT-01]** |
| **Finding 10: Heading Symmetry** | `critic_report.md` | `egm-structural` | **[ACT-NIT-05]** |
| **Finding 11: Colloquial Phrasing** | `critic_report.md` | `egm-style` | **[ACT-NIT-03]** |
| **Finding 12: Audit Log Bloat** | `critic_report.md` | `egm-design` | **[ACT-NIT-08]** |
| **Finding 13: Atomic Writes** | `critic_report.md` | `egm-design` | **[ACT-NIT-08]** |
| **Finding 1: Fix Risk (Local SLM)** | `intermediate_zoom_out_report.md` | `egm-zoom-out` | **[ACT-BLK-06]** |
| **Finding 2: Fix Risk (Vector Sprawl)** | `intermediate_zoom_out_report.md` | `egm-zoom-out` | **[ACT-BLK-06]** |
| **Finding 3: Persistent Enterprise Stack** | `intermediate_zoom_out_report.md` | `egm-zoom-out` | **[ACT-BLK-01]** |
| **Finding 4: Fix Risk (Metamodels)** | `intermediate_zoom_out_report.md` | `egm-zoom-out` | **[ACT-BLK-03]** |
| **Finding 5: Architectural Impasse** | `intermediate_zoom_out_report.md` | `egm-zoom-out` | **[ACT-BLK-05]**, **[ACT-MAJ-08]** |
| **Finding 6: Premature Altitude Drop** | `intermediate_zoom_out_report.md` | `egm-zoom-out` | **[ACT-BLK-01]** |
| **Finding 1: Missing Text Extractor** | `implementation_readiness_report.md` | `egm-readiness` / `details` | **[ACT-BLK-02]** |
| **Finding 2: Unspecified Persistence** | `implementation_readiness_report.md` | `egm-readiness` / `details` | **[ACT-BLK-01]**, **[ACT-BLK-06]** |
| **Finding 3: Missing LLM SDK & Config** | `implementation_readiness_report.md` | `egm-readiness` / `details` | **[ACT-BLK-04]** |
| **Finding 4: Missing `pyproject.toml`** | `implementation_readiness_report.md` | `egm-details` | **[ACT-BLK-04]** |
| **Finding 5: Undefined YAML DSL** | `implementation_readiness_report.md` | `egm-readiness` | **[ACT-MAJ-05]** |
| **Finding 6: Sidecar Schema Gap** | `implementation_readiness_report.md` | `egm-readiness` | **[ACT-MAJ-04]** |
| **Finding 7: Incomplete Test Suite** | `implementation_readiness_report.md` | `egm-readiness` / `details` | **[ACT-MAJ-06]** |
| **Finding 8: Sidecar Collision & State** | `implementation_readiness_report.md` | `egm-readiness` / `details` | **[ACT-MAJ-09]** |
| **Finding 9: Hyperbolic Claims** | `implementation_readiness_report.md` | `egm-style` | **[ACT-NIT-04]** |
| **Finding 10: Missing OWL Reasoner** | `implementation_readiness_report.md` | `egm-details` | **[ACT-BLK-01]** |
| **Finding 11: Hardcoded Threshold** | `implementation_readiness_report.md` | `egm-details` | **[ACT-NIT-07]** |
| **Finding 12: Test Threshold Discord** | `implementation_readiness_report.md` | `egm-style` | **[ACT-NIT-06]** |

---

## 5. Recommended Remediation Roadmap

To prepare this design for production implementation, apply the following sequence of revisions:

1. **Resolve Core Architecture & Prune Enterprise Bloat**:
   - Confirm whether OWL 2 DL and xAPI are external harness prerequisites or can be replaced with standard Pydantic schemas (`schemas/taxonomy.json`) and local JSONL audit logs (`.s3a/audit_log.jsonl`).
   - Standardize storage on a central `.s3a/` workspace cache (`.s3a/catalog.sqlite` or `.s3a/metadata/<sha256>.json`) to eliminate working tree clutter.
   - Clarify that ingestion is 100% virtual indexing; physical file moving is eliminated.
2. **Expand Media & Format Support**:
   - Add `.tar.gz` and `.zip` source archive handling with asset-exclusion filtering (`figures/`, `macros/`).
   - Add `.html` scholarly literature support with citation `<meta>` tag extraction.
3. **Complete Implementation & Packaging Specifications**:
   - Add `src/extractors/text.py` covering multi-format text extraction (PDF, DOCX, TeX, MD).
   - Add `pyproject.toml` declaring dependencies (`python-docx`, LLM SDK, tokenizer) and `s3a-agent` CLI entrypoint.
   - Define concrete LLM provider configurations and structured JSON schema output contracts.
4. **Harden Verification & Test Coverage**:
   - Add `tests/conftest.py` with mock LLM and document fixtures.
   - Add test files covering bibliographic extraction, author matching, and CLI commands.
   - Add the missing `## Risks & Mitigations` section.
