# Goldfish Annotated Review Report

**Target:** `docs/designs/research_artifact_classifier.md` (`full file`)  
**Resolution Context:** User Architectural Clarification (OWL as Agent Role/Job Duties Ontology; xAPI as Agent Task/Job Manual Specification Protocol; S3A System as Native Database)  
**Status:** resolved (Batch applied all approved fixes + S3A Database Integration)  

---

## Executive Architectural Re-Alignment

The Goldfish reviewers (specifically `egm-zoom-out` and `egm-design`) flagged OWL 2 DL and xAPI as "enterprise over-engineering" and "YAGNI" under the assumption that they were intended solely for static document classification and local event logging. 

The user has clarified the foundational architectural design:
* **OWL Web Ontology is the Agent "Job Duties" & Governance Model**: It formally defines agent roles, permitted capabilities, artifact boundaries, and legal state transitions. It specifies what an agent is allowed to inspect, tag, and modify, preventing capability leakage or out-of-scope actions.
* **xAPI Profile is the Agent "Job Manual" & Task Execution Contract**: It serves as a strict runtime harness. Every agent action must conform to an authorized xAPI statement (Actor, Verb, Object, Context, Extensions). Agents cannot take arbitrary actions; they must follow the verifiable "job manual" encoded in the xAPI profile to guarantee zero hallucinated actions or improper file manipulations.

With this intent clarified, the design must be updated to clearly distinguish between **Data Plane** (document fingerprinting, text extraction, fast-path rules) and **Control Plane / Governance** (OWL Job Duties & xAPI Job Manual Harness).

---

## Prioritized Findings & Resolution Plan

### 1. OWL 2 DL Stack & xAPI Profile Critique (`egm-zoom-out`, `egm-design`) - Severity: Blocker
* **Affected Scope**: Lines 48–49, 126–131, 228–281, 388–396, 465–476
* **Discrepancy Description**: Reviewers flagged OWL DL and xAPI as unnecessary enterprise abstractions for local file classification.
* **AI Recommendation**: **CONTEST / REFRAME WITH USER SPECIFICATION**
* **Justification**: The reviewers evaluated these mechanisms as passive file tags. In reality, they form the **Agent Governance Harness**:
  1. OWL specifies agent roles, task permissions, and artifact state constraints ("Job Duties").
  2. xAPI enforces runtime action boundaries, ensuring agents only execute approved task verbs ("Job Manual").
* **Proposed Edit**:
  * Rewrite Section 4 (`OWL Web Ontology Integration`) to define the **Agent Role & Job Duties Ontology** (`s3a:AgentRole`, `s3a:permittedAction`, `s3a:ArtifactBoundary`).
  * Rewrite Section 5 (`xAPI Research Profile`) to define the **Agent Task Execution Contract & Job Manual Harness** (`Actor: Agent`, `Verb: authorized_task`, `Context: constraints`).

---

### 2. Missing Document Text Extractor Module & Multi-Format Parsers (`egm-readiness`, `egm-comprehension`, `egm-details`) - Severity: Blocker
* **Affected Scope**: Target Files list (lines 369–488), Dependencies (line 519)
* **Discrepancy Description**: Downstream extractors require raw text, but no document text extraction module is defined. `python-docx` is omitted, and no `.tex`/`.md` parsing is specified.
* **AI Recommendation**: **PROPOSE FIX**
* **Justification**: An implementing engineer cannot parse documents without a unified text extractor.
* **Proposed Edit**:
  * Add `src/extractors/text.py` declaring `extract_document_text(file_path: Path, max_tokens: int = 2048) -> ExtractedTextResult`.
  * Add `python-docx` to dependencies and define LaTeX preamble and Markdown frontmatter extraction logic.

---

### 3. Real-World Artifact Blindspot: Compound Archives (`.tar.gz`) & Sub-Asset Figures (`egm-design`, `egm-zoom-out`) - Severity: Blocker
* **Affected Scope**: Lines 11, 103, 107–113, 169–179
* **Discrepancy Description**: Academic submissions (e.g., `arXiv-2607.02514v1.tar.gz`) arrive as compressed packages containing LaTeX sources, macros, and figure PDFs (`figures/*.pdf`). The scanner ignores archives and misclassifies sub-figure plots as standalone posters or slides.
* **AI Recommendation**: **PROPOSE FIX**
* **Justification**: Verified directly against workspace context `arXiv-2607.02514v1.tar.gz`.
* **Proposed Edit**:
  * Add `.tar.gz` and `.zip` as recognized container types (`SourceArchive` / `PreprintBundle`).
  * Implement directory/asset exclusion rules: if a folder contains a root manuscript (`main.tex` or root paper), child folders (`figures/`, `images/`, `macros/`) are bound to the parent package and excluded from standalone classification.

---

### 4. Missing Project Packaging Manifest & Concrete LLM SDK (`egm-details`, `egm-readiness`) - Severity: Blocker
* **Affected Scope**: Target Files (lines 369–512), Dependencies (line 519)
* **Discrepancy Description**: Installation commands (`pip install -e .`) and CLI commands (`s3a-agent`) fail without `pyproject.toml`. No LLM SDK or configuration models are defined.
* **AI Recommendation**: **PROPOSE FIX**
* **Justification**: Critical for environment compilation and deterministic LLM fallback.
* **Proposed Edit**:
  * Add `pyproject.toml` with `[project.scripts] s3a-agent = "src.cli:main"`.
  * Designate standard LLM SDK (`google-genai` or `openai`), add `LLMConfig` to `src/config.py`, and add tokenizer dependencies.

---

### 5. Workspace Pollution: Flat Sidecars vs. Centralized `.s3a/` Storage (`egm-design`, `egm-zoom-out`) - Severity: Blocker
* **Affected Scope**: Lines 45–47, 65, 104, 191–226
* **Discrepancy Description**: Scattering `<filename>.<ext>.s3a.json` sidecars next to every file pollutes git working trees, triggers cloud sync churn, and leaves orphan files upon deletion.
* **AI Recommendation**: **PROPOSE FIX**
* **Justification**: Resolves the open question in favor of repository cleanliness and safety.
* **Proposed Edit**:
  * Default metadata persistence to a centralized workspace cache: `<workspace>/.s3a/metadata/<sha256>.json` or an indexed SQLite database, keeping project source trees completely pristine.
  * Provide an opt-in CLI flag for adjacent sidecars when explicit local portability is required.

---

### 6. Emerging Format Blindspot: Scholarly HTML Preprints (`egm-design`, `egm-zoom-out`) - Severity: Major
* **Affected Scope**: Lines 11, 19–21, 37, 103, 171–174
* **Discrepancy Description**: The system assumes published literature is strictly PDF, ignoring modern HTML preprints (e.g., arXiv HTML via LaTeXML/ar5iv, PMC, bioRxiv).
* **AI Recommendation**: **PROPOSE FIX**
* **Justification**: Accurately reflects modern preprint distribution.
* **Proposed Edit**:
  * Add `.html` / `.htm` to supported extensions.
  * Add Scholarly HTML metadata extraction parsing Highwire Press (`<meta name="citation_title">`), Dublin Core, and DOM-embedded DOIs.

---

### 7. Fragile Author Disambiguation & Self-Citation Traps (`egm-design`, `egm-zoom-out`) - Severity: Major
* **Affected Scope**: Lines 84–88, 175–178, 181–185, 206
* **Discrepancy Description**: Naive author name matching conflicts when a researcher downloads their own past published papers (DOI matches *Academic Paper*, but name + local PDF matches *Author Draft*).
* **AI Recommendation**: **PROPOSE FIX**
* **Justification**: Prevents false-positive draft labeling on downloaded literature.
* **Proposed Edit**:
  * Decouple *Authorship* from *Status*. A file is only an `AuthorDraft` if it has active editable source files, recent modification history, or explicit draft headers, even if the user authored it.
  * Enforce minimum page counts ($\ge 3$) for presentations to eliminate single-slide figure false positives.

---

### 8. Architectural Privacy Gate & Token Budgeting (`egm-design`) - Severity: Major
* **Affected Scope**: Lines 150, 186–188, 343, 351–353
* **Discrepancy Description**: Ambiguous files are automatically routed to remote LLMs without an explicit user privacy confirmation, risking silent data exfiltration and API cost spikes.
* **AI Recommendation**: **PROPOSE FIX**
* **Justification**: Protects unreleased intellectual property and prevents token budget exhaustion.
* **Proposed Edit**:
  * Assign status `NeedsReview` when fast-path confidence is $< 0.85$.
  * Require explicit `--allow-remote-llm` flag before transmitting text snippets to cloud endpoints, with batching and spend caps.

---

### 9. Missing Mandatory Section: `## Risks & Mitigations` (`egm-structural`) - Severity: Major
* **Affected Scope**: Lines 340–354
* **Discrepancy Description**: Violates Feature Spec blueprint by omitting a dedicated risks and mitigations section.
* **AI Recommendation**: **PROPOSE FIX**
* **Proposed Edit**: Add `## Risks & Mitigations` mapping operational failure modes (rate limits, malformed metadata, hash mismatch, figure confusion) to concrete architectural mitigations.

---

### 10. Test Suite Expansion & Mock Fixtures (`egm-readiness`, `egm-details`) - Severity: Major
* **Affected Scope**: Lines 489–508, 521–532
* **Discrepancy Description**: The plan omits tests for bibliographic extraction, author matching, CLI commands, and shared mock fixtures (`tests/conftest.py`).
* **AI Recommendation**: **PROPOSE FIX**
* **Proposed Edit**: Add `tests/conftest.py` with mock LLM fixtures, add missing test files, and mandate 90% branch coverage across all modules.

---

### 11. Style & Terminology Polish (`egm-style`, `egm-structural`) - Severity: Nit
* **Affected Scope**: Multiple lines across document
* **Discrepancy Description**: Overused promotional adjectives ("transparent"), imprecise phrasing ("human-editable fingerprints"), and list asymmetries.
* **AI Recommendation**: **PROPOSE FIX**
* **Proposed Edit**:
  * Replace "human-editable fingerprints" with "human-editable metadata manifests containing an immutable content fingerprint".
  * Standardize promotional modifiers to objective technical terms ("plain-text JSON", "heuristic classification").
  * Reconcile poster dimension threshold ($>= 24$ inches / 610mm) and eliminate meta-commentary footer.

---

### 12. Storage Architecture: S3A System as Native Database (User Resolution) - Severity: Blocker
* **Affected Scope**: Lines 96, 127–130, 242–246, 316, 380, 434–436, 458, 497
* **Discrepancy Description**: Reviewers proposed an embedded SQLite database as an ad-hoc local catalog. The user clarified that the S3A system itself is the research database and authoritative repository.
* **AI Recommendation**: **PROPOSE FIX**
* **Justification**: Eliminates SQLite as an unnecessary middleman. The agent's `src/s3a/bridge.py` directly ingests verified manifests, content-addressed fingerprints, and ontology relationships into the S3A Research Database and S3A Knowledge Graph via the S3A harness client. Local `.s3a/metadata/` serves strictly as a temporary non-destructive staging buffer.
* **Applied Edit**: Replaced all SQLite references across the architecture diagram, CUJs, component specifications, and configuration models with direct S3A System Database integration.

---

### 13. System Integration: S3A Harness Addon Architecture (User Resolution) - Severity: Blocker
* **Affected Scope**: Overview (lines 13–18), Technical Plan (lines 104–140), Component Breakdown (lines 242–252), Target Files (`src/config.py`, `src/s3a/bridge.py`)
* **Discrepancy Description**: The system treated S3A as a generic database endpoint without leveraging S3A's native Harness Addon and Mobile Tile storage model (`s3a-storage`).
* **AI Recommendation**: **PROPOSE FIX**
* **Justification**: S3A features a dedicated **Harness Addon** interfacing with `s3a-harness` (the directive interpreter and agent role supervisor). Integrating through the Harness Addon allows the classifier agent to package research artifacts directly into S3A **Capsule Tiles** (standalone papers, notes, slides) and **Compound Tiles** (multi-file source packages like `.tar.gz`), executing signed Directive Tiles over `gate://` or local IPC.
* **Applied Edit**: Formalized S3A Harness Addon integration in the system architecture diagram, component specifications, and bridge contracts.

---

### 14. Official Upstream Crate Alignment: `s3a-storage/crates` (User Resolution) - Severity: Blocker
* **Affected Scope**: Entire System Architecture & Component Mapping
* **Discrepancy Description**: The initial Goldfish review swarm audited the document without discovering or reading the official S3A storage codebase ([`github.com/ashleycribb/s3a-storage/tree/main/crates`](https://github.com/ashleycribb/s3a-storage/tree/main/crates)), leading to false assumptions of missing capabilities and misplaced YAGNI critiques.
* **AI Recommendation**: **PROPOSE FIX**
* **Justification**: The upstream codebase already contains the exact native implementations required:
  1. `crates/s3a-harness`: Official Model Context Protocol (MCP 2024-11-05 & JSON-RPC 2.0) server featuring built-in supervisory human gates (`preflight_check`, `request_human_gate`, `record_human_decision`, `record_ai_step`) and xAPI execution tools.
  2. `crates/s3a-pack-scholar`: `ADDON_EDU` domain pack mapping academic papers, DOIs, citation counts, and 3D Hilbert spatial coordinates to Hyper-Tiles 10–15.
  3. `crates/s3a-pack-ontology`: `ADDON_ONTOLOGY` domain pack mapping OWL axioms and ontology rules.
  4. `crates/s3a-lrs-server`: Native xAPI 1.0.3 REST and IEEE P2997 ELR server.
  5. `crates/s3a-core` & `crates/s3a-engine`: Zero external database binary storage engine (`*.s3a`).
* **Applied Edit**: Grounded the entire technical design, component breakdown, and bridge contracts in the native `s3a-storage/crates` workspace.

---

### 15. Native S3A Agent Template Registration: `agents/scholar_classifier.toml` (User Resolution) - Severity: Blocker
* **Affected Scope**: Target Files list, System Integration & Bridge Specifications
* **Discrepancy Description**: The system lacked a standardized agent configuration file recognizable by `s3a-harness` as an official native template agent.
* **AI Recommendation**: **PROPOSE FIX**
* **Justification**: The upstream repository defines native production agents in TOML format (e.g. [`agents/scholar_reviewer.toml`](https://github.com/ashleycribb/s3a-storage/blob/main/agents/scholar_reviewer.toml)), which `s3a-harness` natively parses via `AgentConfig::load_file()`. Packaging the classifier as `agents/scholar_classifier.toml` allows S3A to discover, validate, and execute it as a recognized, governed agent with pre-configured run limits, decision thresholds, safe defaults, and tool whitelists.
* **Applied Edit**:
  * Created `agents/scholar_classifier.toml` adhering to `s3a-harness` `AgentConfig` schema (`id = "scholar_classifier"`, dual-model escalation `llama3.2:3b` -> `llama3.3:70b`, safe default `"ask_human"`, and whitelisted MCP tools).
  * Updated `docs/designs/research_artifact_classifier.md` with Section 7 and registered `agents/scholar_classifier.toml` in Target Files.
