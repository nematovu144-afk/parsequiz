# Quiz Parser — Document-to-Quiz Conversion Engine

## Architecture

```
quiz-parser/
├── app/
│   ├── main.py                  # FastAPI entry, CORS, lifespan
│   ├── config.py                # Pydantic Settings (env-driven)
│   ├── api/
│   │   ├── upload.py            # POST /upload  — file ingestion
│   │   ├── parse.py             # GET  /parse/{job_id} — poll status / results
│   │   └── export.py            # POST /export  — JSON/XLSX/CSV download
│   ├── core/
│   │   ├── job_store.py         # SQLite-backed job registry (app/db/)
│   │   └── exceptions.py        # Domain exceptions
│   ├── db/
│   │   ├── base.py              # Async engine, session factory, declarative base
│   │   └── models.py            # JobRecord ORM model
│   ├── parsers/
│   │   ├── base.py              # Abstract parser protocol
│   │   ├── docx_parser.py       # python-docx extractor
│   │   ├── pdf_parser.py        # pdfplumber extractor
│   │   ├── txt_parser.py        # Plain-text extractor
│   │   └── delimiter.py         # Correct-answer delimiter detection
│   ├── schemas/
│   │   └── quiz.py              # Pydantic models (Question, ParseJob, etc.)
│   ├── services/
│   │   ├── orchestrator.py      # Pipeline: extract → detect → normalise → validate
│   │   └── validator.py         # Structural validation & flagging
│   ├── llm/
│   │   └── fallback.py          # LLM-based extraction for messy docs
│   └── export/
│       └── exporters.py         # JSON / XLSX / CSV serializers
├── tests/
├── frontend/                    # React / HTML+Tailwind live editor
├── requirements.txt
└── .env.example
```

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env              # add LLM keys if needed
uvicorn app.main:app --reload
```

## API Flow

1. `POST /api/upload`  → returns `{ job_id }`, kicks off async parsing
2. `GET  /api/parse/{job_id}` → poll until `status: "done"`, returns questions[]
3. `POST /api/export` → send edited questions[], get back JSON/XLSX/CSV file
