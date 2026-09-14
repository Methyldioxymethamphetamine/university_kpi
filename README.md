# KPI Pipeline — University Data Acquisition, Extraction & Verification

A robust, provenance-preserving pipeline designed to acquire, parse, verify, and index public self-disclosure documents from higher education institutions (such as Indian NIRF submission PDFs and US Common Data Set HTML reports).

---

## 🎯 Project Overview & Core Philosophy

The primary deliverable of this pipeline is to benchmark key performance indicators (KPIs) across institutions while maintaining an **unbroken chain of evidence**. Every single extracted metric traces back to its exact bounding box geometry, page number, and SHA-256 hash of the immutable source document.

### The Problem: Silent Failure in Document Parsers
Many academic disclosure PDFs (e.g., NIRF submissions) contain `/Rotate 90` internal text matrices and non-standard table formats. Naive parsers often read these documents smoothly without crashing, but silently interleave adjacent table rows—creating plausible-looking, fluent output where numbers are linked to the wrong labels.

Additionally, data entry errors in official filings can skew automated benchmark analyses. For example, in Sandip SITRC's 2025 submission, a salary field lists digits as `3750000` but text as `Three Lakh Seventy Five Thousand` (a 10× discrepancy). A naive digits-only parser would erroneously report Sandip outperforming top-tier institutions on graduate salary.

### Operating Principle
> **"A crash is a good outcome. A plausible wrong number shown to a decision-maker is the failure we exist to prevent."**

---

## 🏗️ Architecture & Pipeline Stages

```
   ┌────────────────┐     ┌─────────────────┐     ┌──────────────────┐
   │  Acquisition   │ ──► │   Conversion    │ ──► │  Classification  │
   │ (Scrapy/HTTPS) │     │ (Docling JSON)  │     │   & Profiling    │
   └────────────────┘     └─────────────────┘     └──────────────────┘
            │                                               │
            ▼                                               ▼
   ┌────────────────┐     ┌─────────────────┐     ┌──────────────────┐
   │ Raw Immutable  │     │ 3-State Engine  │ ──► │ Index & UI Review│
   │  Store (SHA)   │     │ (Digits/Words)  │     │ (Postgres/Flask) │
   └────────────────┘     └─────────────────┘     └──────────────────┘
```

The pipeline operates across discrete, decoupled stages:

1. **Acquisition ([acquire/](file:///home/dushyant/Downloads/kpi/acquire))**: Fetches PDFs and HTML reports using Scrapy. Files are stored strictly as immutable blobs under `raw/sha256/` indexed by SHA-256 hash. Zero parsing occurs during acquisition.
2. **Conversion ([convert/](file:///home/dushyant/Downloads/kpi/convert))**: Converts documents to Docling JSON (`save_as_json()`), retaining full spatial geometry, page indexes, and bounding box coordinates (`pypdfium2`). Export to Markdown/HTML is strictly prohibited to prevent data loss.
3. **Classification & Fingerprinting ([classify/](file:///home/dushyant/Downloads/kpi/classify), [fingerprint/](file:///home/dushyant/Downloads/kpi/fingerprint))**: Identifies document structures, form types (e.g., NIRF Overall, CDS Section B/C), and checks rotation matrices (`/Rotate 90`).
4. **Extraction & Reconciliation ([extract/](file:///home/dushyant/Downloads/kpi/extract))**: Extracts cell geometry and runs a 3-State Checksum Engine (`CONFIRMED`, `CONFLICTING`, `UNVERIFIED`) comparing digit figures against spelled-out word amounts.
5. **Discovery & Review ([discovery/](file:///home/dushyant/Downloads/kpi/discovery), [review/](file:///home/dushyant/Downloads/kpi/review), [scripts/app.py](file:///home/dushyant/Downloads/kpi/scripts/app.py))**: Generates metric candidates for unmapped fields and presents them via a Flask web application for human-in-the-loop review.
6. **Storage & Indexing ([db/](file:///home/dushyant/Downloads/kpi/db))**: Stores sources, execution runs, and vector embeddings in PostgreSQL 17 with `pgvector`.

---

## 📁 Repository Structure

```
kpi/
├── acquire/             # Scrapy spiders, storage engine, manifest logging
├── classify/            # Format detection, MIME sniffing, label extraction
├── convert/             # Docling conversion wrapper and bounding-box preservation
├── extract/             # Bounding box spatial analysis & digits-vs-words checksum engine
├── fingerprint/         # Document structural layout fingerprinting & matcher
├── discovery/           # KPI candidate generator and dictionary matcher
├── review/              # Review queue management for unmapped fields
├── profiles/            # Form templates (YAML) for NIRF & US CDS layouts
├── db/                  # PostgreSQL schema definitions (schema.sql)
├── scripts/             # CLI runners & Flask Web Application
│   ├── run_acquire.py   # Step 1: Run source crawlers
│   ├── run_classify.py  # Step 2: Classify acquired raw artifacts
│   ├── run_convert.py   # Step 3: Convert PDF/HTML to Docling JSON
│   ├── run_extract.py   # Step 4: Extract cell data & compute checksums
│   └── app.py           # Web UI for browsing extraction provenance & review queue
├── tests/               # Pytest suite validating rotation, checksums & export rules
├── findings/            # Source analysis, checksum study & NIRF coverage docs
├── notes/               # Methodology catalogue, spec notes & dictionary defects
├── CLAUDE.md            # Non-negotiable project laws (P-1 to P-16)
├── INSTRUCTIONS.md      # Workflow rules, role splits, and setup steps
├── pyproject.toml       # Python package metadata and dependencies
└── docker-compose.yml   # PostgreSQL 17 + pgvector service definition
```

---

## ⚡ Key Governance Laws

The project follows non-negotiable laws documented in [CLAUDE.md](file:///home/dushyant/Downloads/kpi/CLAUDE.md):

* **P-2 (No Lossy Export)**: Docling output is stored *only* as JSON (`save_as_json()`). Markdown/HTML exports drop page and bounding-box provenance.
* **P-3 (Layer Boundaries)**: Acquisition returns raw bytes and HTTP headers only. No parsing inside spiders.
* **P-4 & P-5 (Immutability)**: Files under `raw/` are never overwritten. Extracted values are inserted with a fresh `run_id`, never updated in place.
* **P-7 (No Auto-Resolution)**: Digits vs. words conflicts (such as Sandip's 10x gap) are flagged as `CONFLICTING`, retaining both values for human review.
* **P-13 & P-15 (Strict Matching)**: Unrecognized pages return zero values loudly. Candidate mappings are never auto-accepted regardless of confidence score.

---

## 🛠️ Requirements & Technology Stack

* **Language**: Python >= 3.11
* **Acquisition**: Scrapy >= 2.14
* **Conversion**: Docling >= 2.0, Docling Core >= 2.83
* **Geometry**: pypdfium2 >= 4
* **Database**: PostgreSQL 17 with `pgvector`
* **Web Review UI**: Flask >= 3.1
* **Validation & Testing**: Pytest >= 8, Pydantic >= 2, OpenPyXL, Filetype

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
Ensure Python 3.11+ and Docker are installed on your system.

### 2. Set Up Virtual Environment & Dependencies

```bash
# Clone or navigate to repository root
cd kpi

# Create virtual environment
uv venv .venv
source .venv/bin/activate

# Install package in editable mode with development dependencies
uv pip install -e ".[dev]"
```

*Note: Alternatively, using standard `pip`:*
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Pre-warm Docling Layout Models
Download and cache the required table layout and TableFormer models:
```bash
python3 -c "from docling.document_converter import DocumentConverter; DocumentConverter()"
```

### 4. Start the Database
Spin up the PostgreSQL container with `pgvector`:
```bash
docker compose up -d
docker compose exec db psql -U postgres -d kpi -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

---

## 💻 Running the Pipeline

Execute the pipeline stages sequentially:

### Stage 1: Acquisition
Crawl source institutions (IIT Bombay, Sandip SITRC, MIT) and store raw files immutably:
```bash
python3 scripts/run_acquire.py
```

### Stage 2: Classification
Inspect raw artifacts, detect MIME types, and tag file formats:
```bash
python3 scripts/run_classify.py
```

### Stage 3: Conversion
Convert PDFs and HTML files into structured Docling JSON preserving bounding boxes:
```bash
python3 scripts/run_convert.py
```

### Stage 4: Extraction & Verification
Extract geometry-backed table values and run the 3-state checksum engine:
```bash
python3 scripts/run_extract.py
```

### Stage 5: Web UI & Review Queue
Launch the Flask web interface to inspect live extraction provenance and handle review candidates:
```bash
python3 scripts/app.py
```
Open your browser at `http://127.0.0.1:5000` to interact with:
* **Inventory & Provenance Route**: View raw document extractions alongside full page and coordinate citations.
* **Scrape & Review Route**: Test candidate matchers against target KPIs and inspect flagged checksum conflicts.

---

## 🧪 Testing

Run the test suite to verify pipeline integrity, rotation handling, and checksum rules:

```bash
PYTHONPATH=. pytest
```

### Verified Test Scope
* `test_p1_rotation_regression.py`: Asserts correct text matrix extraction on 90-degree rotated PDFs.
* `test_p2_no_lossy_export.py`: Enforces P-2 compliance (prohibits Markdown/HTML Docling exports).
* `test_word_number.py`: Verifies word-to-number parsing accuracy across English and Indian numeric words (Lakh/Crore).
* `test_checksums_three_state.py`: Tests `CONFIRMED`, `CONFLICTING`, and `UNVERIFIED` reconciliation states.
* `test_classify_labels.py`: Validates MIME detection and document layout classification.

---

## 📖 Further Reading & Documentation

* [CLAUDE.md](file:///home/dushyant/Downloads/kpi/CLAUDE.md) — Mandatory project laws and decision log.
* [INSTRUCTIONS.md](file:///home/dushyant/Downloads/kpi/INSTRUCTIONS.md) — Team procedures and phase guidelines.
* [findings/](file:///home/dushyant/Downloads/kpi/findings) — Source investigation notes & defect analysis.
* [db/schema.sql](file:///home/dushyant/Downloads/kpi/db/schema.sql) — Database schema definitions.
