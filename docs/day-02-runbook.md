# Day 2: Evidence workflow runbook

## Delivered workflow

The Streamlit application now:

1. accepts PDF, Markdown and plain-text research sources;
2. stores the original source bytes in the private Backblaze B2 bucket;
3. extracts selectable PDF or text content;
4. stores the extracted text and extraction metadata in B2;
5. creates deterministic, traceable evidence-card candidates;
6. presents an interface for editing claims and marking them approved, rejected or pending; and
7. stores the reviewed card collection in B2 as JSON.

The card generator is deliberately review-first. It ranks high-signal source sentences using transparent rules rather than presenting unverified AI summaries as approved evidence.

## Codespaces setup

```bash
# Switches to the Day 2 branch and installs the evidence-workflow dependencies.
git fetch origin
git switch feat/day-02-evidence-workflow
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Keep the existing populated `.env` file. Optionally add:

```dotenv
EVIDENCECAST_B2_PREFIX=evidencecast
```

## Run tests

```bash
# Runs the extraction, evidence-card and review-state unit tests.
pytest -q
```

## Run the interface

```bash
# Starts the EvidenceCast evidence-review interface in Codespaces.
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

In Codespaces, open the forwarded port `8501` in the browser. Set the port visibility to private while credentials and private research sources are in use.

## B2 object layout

```text
{prefix}/sources/{sha256[:2]}/{source_sha256}/
  original/{sanitised_filename}
  derived/extracted.txt
  derived/extraction.json
  reviews/evidence-cards.json
```

The original source object includes its SHA-256 digest in B2 object metadata. The extraction record includes the original and derived object hashes and URIs. Evidence cards retain source excerpts and PDF page numbers where available.

## Review behaviour

- `pending`: no final decision has been made;
- `approved`: the edited claim is authorised for downstream media planning;
- `rejected`: the candidate must not be used for generation.

The review collection is `completed` only when no card remains pending.

## Known limitation

`pypdf` extracts selectable PDF text. Image-only scanned PDFs require OCR, which is intentionally outside this milestone. The application reports this clearly rather than silently inventing or omitting evidence.
