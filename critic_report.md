# Critic Review Report (Stage 7)

**Target:** `docs/designs/research_artifact_classifier.md` (`FeatureRange`: lines 1..355)  
**Reviewers:** Design Critic (`egm-design`), Structural Layout Reviewer (`egm-structural`), Technical Style Reviewer (`egm-style`)  
**Standard:** `resources/document_standards/feature-spec-standard.md`  
**Inspected Context:** Target specification and `arXiv-2607.02514v1.tar.gz` (LaTeX source bundle, figures, macros, bib, and emerging web/HTML preprint formats).

---

## Executive Summary
The Feature Specification presents a detailed taxonomic approach and clear Critical User Journeys, but suffers from significant architectural blindspots when tested against real academic workflows. The design treats research files as isolated, flat documents, ignoring compound archives (`.tar.gz`), sub-asset figures (`figures/*.pdf`), and modern scholarly HTML preprints. Furthermore, writing adjacent sidecars threatens to clutter researcher working trees, and the unconstrained fallback to external LLMs introduces privacy risks and potential token cost explosions.

---

## Consolidated Findings

### 🔴 Blockers

#### 1. Lack of Compound Archive (`.tar.gz` / `.zip`) and Sub-Asset Figure Handling
* **Reviewer**: Design Critic (`egm-design`)
* **Affected Scope**: Lines 11, 103, 107–113, 169–179
* **Critique & Flaw**:
  Academic preprints and researcher submissions (e.g., `arXiv-2607.02514v1.tar.gz`) are distributed as compressed archives containing nested projects (`main.tex`, `figures/*.pdf`, style definitions, `.bib` files). 
  1. The specification completely omits archive extensions (`.tar.gz`, `.zip`) from its ingestion scope.
  2. If an archive is unpacked, the scanner treats every auxiliary figure PDF (`figures/gradual_timing.pdf`) as an independent top-level research artifact, attempting to compute geometry, check for DOIs, and misclassifying single-page plots as independent *Conference Posters* or *Conference Presentations*.
* **Required Remediation**: Introduce a compound artifact / package concept (`s3a:CompoundArtifact` or `SourcePackage`). Add bundle introspection for `.tar.gz`/`.zip` to locate the primary document entrypoint (`main.tex`, root compiled PDF) and establish asset exclusion rules so sub-figures are bound to the parent manuscript rather than classified independently.

#### 2. Workspace Pollution, VCS Clutter, and Unresolved Sidecar Storage Strategy
* **Reviewer**: Design Critic (`egm-design`) & Style Reviewer (`egm-style`)
* **Affected Scope**: Lines 45–47, 65, 104, 191–226
* **Critique & Flaw**:
  The specification mandates dropping an adjacent `<filename>.s3a.json` sidecar alongside every single scanned file:
  1. In complex research trees, adjacent sidecars double file counts, pollute Git working trees, trigger cloud sync thrashing (Dropbox, Google Drive), and leave orphan `.s3a.json` debris when files are moved or deleted.
  2. Internal contradiction: Line 65 lists "Metadata Tag Persistence Strategy" as an unresolved Open Question (debating adjacent files vs. central `.s3a/` directory vs. in-file metadata), yet lines 104 and 191–226 prematurely commit to hardcoded adjacent sidecars.
* **Required Remediation**: Resolve the open question in favor of a centralized workspace metadata store (e.g., `<workspace>/.s3a/metadata/<sha256>.json` or an indexed SQLite/JSON-LD cache in `.s3a/`), leaving project directories clean. If adjacent sidecars are supported, make them an opt-in mode with automatic `.gitignore` generation.

---

### 🟡 Major Issues

#### 3. Inability to Handle Modern Scholarly HTML Preprints & Web Bundles
* **Reviewer**: Design Critic (`egm-design`)
* **Affected Scope**: Lines 11, 19–21, 37, 103, 171–174
* **Critique & Flaw**:
  The specification strictly associates published literature with static `.pdf` files. Modern scholarly publishing is shifting toward HTML-first delivery (e.g., arXiv HTML via LaTeXML/ar5iv, PubMed Central, bioRxiv). Researchers frequently save papers as `.html`/`.htm` or web archives. The current design lacks support for `.html` files, cannot parse standard scholarly HTML metadata headers (Highwire Press `<meta name="citation_title">`, Dublin Core, PRISM, schema.org), and ignores HTML preprints entirely.
* **Required Remediation**: Add `.html`/`.htm` to core supported formats and equip the parser with a Scholarly HTML metadata extractor that parses citation `<meta>` headers and resolves DOIs from DOM structures.

#### 4. Fragile Author Disambiguation and High False-Positive Risk
* **Reviewer**: Design Critic (`egm-design`)
* **Affected Scope**: Lines 84–88, 175–178, 181–185, 206
* **Critique & Flaw**:
  The deterministic rule engine relies on naive string matching of author names from `user_profile.json` against the document's first page:
  1. When a researcher downloads a published copy of their own paper (which has a registered DOI and their name), the rules conflict (DOI matches *Academic Paper*, but name + local PDF matches *Author Draft*).
  2. Researchers with common surnames suffer false positives where downloaded external literature authored by a namesake is classified as an `AuthorDraft`.
  3. Single-page plots and widescreen supplementary figures are vulnerable to being misclassified as *Conference Presentations* or *Conference Posters*.
* **Required Remediation**: Disambiguate author identity using ORCIDs and explicit manuscript status indicators. Require verifiable project markers for `AuthorDraft` (editable source files with recent write activity or active git tracking), and enforce minimum page-count thresholds ($\ge 3$ consecutive slides for presentations) to eliminate figure PDF misclassifications.

#### 5. Unbounded LLM Token Costs & Fallback Rate Limiting
* **Reviewer**: Design Critic (`egm-design`)
* **Affected Scope**: Lines 116, 150–152, 186–188, 351–353
* **Critique & Flaw**:
  Routing every artifact that fails the deterministic fast-path ($< 0.85$ confidence) to an LLM with a 2,000-token payload creates severe infrastructure bottlenecks in large academic workspaces. In a repository of 5,000 ambiguous files, this triggers 5,000 external API calls and consumes $\sim 10,000,000$ tokens, causing HTTP 429 rate limits, excessive API costs, and scanning delays.
* **Required Remediation**: Implement a tiered classification model: (1) deterministic rules, (2) offline lightweight local classifier (e.g., local embedding model / small SLM requiring zero external tokens), and (3) external LLM fallback strictly as an explicit, user-authorized opt-in for unresolved root documents with global token budget caps.

#### 6. Privacy Invariant Breach: Silent External LLM Data Transmission
* **Reviewer**: Design Critic (`egm-design`)
* **Affected Scope**: Lines 150, 186–188, 343
* **Critique & Flaw**:
  Line 343 states: *"Sensitive unreleased manuscripts and private lab notes are never transmitted to external APIs unless LLM fallback is explicitly authorized."* However, the technical architecture in lines 150 and 186–188 automatically feeds ambiguous text directly into `LLMClassifierClient` without a user confirmation prompt or privacy gate, risking silent exfiltration of unreleased manuscripts and private notes.
* **Required Remediation**: Enforce an architectural privacy gate: assign a local status of `NeedsReview` when fast-path confidence is low, and require explicit user flags (e.g., `--allow-remote-llm`) before transmitting snippets to external endpoints.

#### 7. Missing Mandatory Blueprint Section: `## Risks & Mitigations`
* **Reviewer**: Structural Goldfish (`egm-structural`)
* **Affected Scope**: Lines 340–354
* **Critique & Flaw**:
  The Feature Specification Standard explicitly mandates a dedicated `Risks & Mitigations` section detailing failure modes, security implications, scalability limits, and concrete mitigations. The current draft scatters generic LLM failure modes in the problem statement and lists standard NFRs, but lacks a formal risk and mitigation matrix.
* **Required Remediation**: Add a dedicated `## Risks & Mitigations` section mapping failure modes (token exhaustion, malformed sidecars, hashing bottlenecks, network failures) to explicit mitigations.

#### 8. Conceptual Imprecision: Fingerprint vs. Manifest
* **Reviewer**: Technical Style Reviewer (`egm-style`)
* **Affected Scope**: Lines 13, 29, 45, 98
* **Critique & Flaw**:
  The document repeatedly refers to "transparent and human-editable metadata fingerprints". A cryptographic fingerprint (SHA-256) is deterministic, immutable, and strictly non-editable; modifying it invalidates the hash. The editable artifact is the sidecar manifest.
* **Required Remediation**: Replace "human-editable metadata fingerprints" with "human-editable metadata sidecars/manifests containing an immutable content fingerprint".

#### 9. Promotional Buzzword Repetition ("Transparent")
* **Reviewer**: Technical Style Reviewer (`egm-style`)
* **Affected Scope**: Lines 13, 29, 45, 46, 77, 80, 87, 98, 104, 121, 191, 302, 314
* **Critique & Flaw**:
  The adjective "transparent" appears more than 10 times in 355 lines as marketing emphasis.
* **Required Remediation**: Replace subjective promotional modifiers with precise technical terms: "plain-text JSON sidecar", "decentralized manifest", or "user-visible filesystem metadata".

---

### 🟢 Nits

#### 10. Heading Hierarchy & Section Naming Symmetry
* **Reviewer**: Structural Goldfish (`egm-structural`)
* **Affected Scope**: Lines 9–30, 35–51
* **Critique & Flaw**:
  The document bifurcates problem definition across `## Overview` and `## The Problem`. Furthermore, `## Goals` has mixed list formatting (first 3 entries have indented sub-bullets, last 3 are single-line descriptions).
* **Required Remediation**: Unify heading nomenclature under standard `## Problem Statement` and standardize list layout symmetry in `## Goals`.

#### 11. Colloquial Phrasing and Slang
* **Reviewer**: Technical Style Reviewer (`egm-style`)
* **Affected Scope**: Lines 27, 59, 326, 336, 347, 352
* **Critique & Flaw**:
  Informal phrases like "black-box vector stores", "on the fly", "context window dumps", and "bonded to files" should be replaced with formal technical descriptions ("centralized vector databases", "dynamically generated", "submitting entire documents", "associated via digests").

#### 12. Compilation Thrashing and xAPI Audit Log Bloat
* **Reviewer**: Design Critic (`egm-design`)
* **Affected Scope**: Lines 247–280, 347–349
* **Critique & Flaw**:
  Recompiling LaTeX updates `main.pdf` frequently, altering hashes, invalidating caches, and bloating `.s3a/events.jsonl`.
* **Required Remediation**: Add a 30–60 second debounce window on file modification listeners and implement audit log rotation.

#### 13. Concurrency & Atomic Write Omissions
* **Reviewer**: Design Critic (`egm-design`)
* **Affected Scope**: Lines 450–470
* **Critique & Flaw**:
  Concurrent processes scanning or editing metadata risk race conditions and corruption without atomic write-to-temp-and-rename mechanics.
