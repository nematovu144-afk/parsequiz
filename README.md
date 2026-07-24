# ParseQuiz — Document-to-Quiz Conversion Engine

## Architecture

```
quiz-parser/
├── app/
│   ├── main.py                  # FastAPI entry, CORS, rate limiter, lifespan
│   ├── config.py                # Pydantic Settings (env-driven)
│   ├── api/
│   │   ├── upload.py            # POST /upload  — file ingestion (rate-limited)
│   │   ├── parse.py             # GET  /parse/{job_id} — poll status / results
│   │   └── export.py            # POST /export  — JSON/XLSX/CSV download (rate-limited)
│   ├── core/
│   │   ├── job_store.py         # Postgres-backed job registry (app/db/)
│   │   ├── rate_limit.py        # Shared slowapi Limiter instance
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
├── Dockerfile
├── docker-compose.yml           # Postgres + API, one command for local dev
├── render.yaml                  # Render Blueprint: free Postgres + web service
├── requirements.txt
├── requirements-dev.txt         # + pytest, ruff
└── .env.example
```

## Quick Start

Needs a Postgres database — the fastest way to get one locally is Docker:

```bash
docker compose up          # Postgres + API + frontend, all on http://localhost:8000
```

Or run it without Docker, against your own Postgres instance:

```bash
pip install -r requirements.txt
cp .env.example .env              # set DATABASE_URL, add LLM keys if needed
uvicorn app.main:app --reload
```

Either way, open **http://localhost:8000** — the frontend and API are served from the same origin.

## API Flow

1. `POST /api/upload`  → returns `{ job_id }`, kicks off async parsing (rate-limited: 10/min per IP)
2. `GET  /api/parse/{job_id}` → poll until `status: "done"`, returns questions[]
3. `POST /api/export` → send edited questions[], get back JSON/XLSX/CSV file (rate-limited: 30/min per IP)

## Deploy

`render.yaml` provisions a free Postgres instance + a Docker web service in one go:

1. Push this repo to GitHub.
2. On [render.com](https://render.com): **New +** → **Blueprint** → select the repo.
3. Render reads `render.yaml`, creates the database, wires `DATABASE_URL` automatically, and deploys.

You get a permanent `https://…onrender.com` URL — works from any device, and safe to share with anyone.

## Development

```bash
pip install -r requirements-dev.txt
pytest -q            # 45 tests — parsers, validator, exporters, job store, API
ruff check app tests  # lint (config in pyproject.toml)
```
