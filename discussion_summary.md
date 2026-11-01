# Context & Problem Formulation: Research Artifact Classifier & S3A Ingestion Agent

## 1. Context & Objectives
Researchers accumulate heterogeneous files across local folders and cloud storage without consistent structure. These folders contain mixed formats (`.pdf`, `.docx`, `.pptx`, `.tex`, `.md`) serving different functional roles. Existing automated tooling frequently misclassifies these artifacts or hallucinates semantic labels, corrupting downstream Knowledge Graphs, Directed Acyclic Graphs (DAGs), Retrieval-Augmented Generation (RAG) indexes, and physical folder hierarchies.

The objective is an AI agent system that accurately classifies, tags, and organizes research artifacts into the S3A system using:
1. **Target Artifact Taxonomy**:
   - Published Academic Papers (external reference literature, peer-reviewed articles)
   - Research Notes (informal notes, lab logs, brainstorming scratchpads, reading summaries)
   - In-Progress Manuscripts / Author Drafts (papers actively being written by the researcher for publication)
   - Conference Posters (visual summaries, large-format single-sheet designs)
   - Conference Presentations (slide decks, talk scripts, presentation decks)
2. **Formal Semantic Framework**:
   - **xAPI Profile**: Formal actor-verb-object statements capturing researcher interaction lifecycle (e.g., `drafted`, `annotated`, `presented`, `filed`).
   - **OWL Web Ontology**: Explicit knowledge model formalizing classes, subclass relationships, properties, and constraints for research artifacts.
   - **S3A System / Harness**: Target repository and workflow execution harness for ingest, verification, and graph construction.
3. **Strict Reliability & Zero-Hallucination Invariant**:
   - Multi-stage deterministic inspection (file format, layout, structure, bibliographic metadata, author attribution) before LLM inference.
   - Strict human-in-the-loop review gating before any destructive or relocational file operations.

---

## 2. Technical Stress-Testing & Critical Vulnerabilities

| Vulnerability / Failure Mode | Root Cause | Architectural Implication |
| :--- | :--- | :--- |
| **Draft vs. Published Paper Confusion** | Author drafts compiled to PDF often mimic IEEE/ACM two-column or Springer published formats. | Classification cannot rely purely on layout. The system must verify local author identity, lack of publication metadata (e.g., registered DOI, volume/issue), or file modification recency against active source files (`.tex`, `.docx`). |
| **Poster vs. Slide Presentation Confusion** | Both frequently share `.pptx` or `.pdf` formats. | Aspect ratio, page count, and physical page dimension inspection must be deterministic gates (e.g., single page with large dimensions `A0/36x48` indicates a poster; multi-page 16:9 indicates slides). |
| **Path Breakage & Relocation Damage** | Moving files breaks relative paths in LaTeX (`\input`, `\includegraphics`), code repositories, and cloud sync roots. | Destructive file movement must be separated from semantic tagging. The agent should default to virtual tagging and symlinking/indexing in S3A before any physical directory restructuring. |
| **Semantic Drift in OWL Generation** | Unconstrained LLM-generated OWL triples produce schema inconsistencies and invalid URIs. | The OWL ontology must be fixed and versioned. The agent must map files to predefined ontology individuals and schema classes via validated Pydantic/JSON-Schema payloads rather than free-form RDF authoring. |
| **xAPI Overkill vs. State Management** | Generating high-frequency xAPI statements without an LRS (Learning Record Store) or audit consumer adds unnecessary latency. | xAPI statements must be lightweight, emitted as event logs for provenance, and decoupled from the synchronous classification pipeline. |

---

## 3. Scope Boundaries

### In Scope
- Static and deterministic feature extraction across target formats (`.pdf`, `.docx`, `.pptx`, `.tex`, `.md`, `.txt`).
- Domain-aware ontology mapping grounded in an OWL specification.
- Structured provenance logging using an xAPI research profile.
- Controlled ingestion pipeline targeting S3A storage and metadata indexing.
- Verification gates with dry-run previews to prevent unauthorized file mutation.

### Out of Scope
- Direct peer-review grading or scientific validity scoring of research content.
- Automatic modification of paper contents or rewriting draft text.
- Full desktop OS shell automation outside configured workspace and cloud folders.
