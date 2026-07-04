# CBSE Class 10 Math Question Bank Builder

Local-first prototype for uploading CBSE Class 10 Mathematics PDFs, extracting questions, separating options, cropping diagrams, tagging metadata, and exporting structured JSON.

The app uses PyMuPDF for native PDF extraction and SQLite for local storage.

## Run

Double-click:

```text
run_portal.bat
```

Or run manually:

```powershell
python -m pip install -r requirements.txt
python app\server.py
```

Open:

```text
http://127.0.0.1:8000
```

## Current MVP

- Upload one PDF at a time.
- Store uploaded PDFs under `data/uploads`.
- Extract text from native PDFs with PyMuPDF, with a fallback parser for simple PDFs.
- Segment CBSE-style questions from Q1 to Q38.
- Auto-tag question type, marks, topic, options, and confidence with rule-based heuristics.
- Crop diagrams separately when the PDF contains an embedded diagram.
- Render questions as written text, not full-question images.
- Persist source PDFs and questions in SQLite.
- Admin UI for upload, search, filtering, verification, and JSON export.

## API

- `POST /api/pdfs/upload`
- `GET /api/pdfs/{id}/status`
- `GET /api/pdfs/{id}/questions`
- `GET /api/questions?topic=&marks=&type=&verified=`
- `GET /api/questions/{id}`
- `PATCH /api/questions/{id}`
- `POST /api/questions/{id}/verify`

## Tests

```powershell
python -m unittest discover tests
```

## Next Upgrade Steps

1. Add OCR routing for scanned PDFs.
2. Move processing into Celery + Redis.
3. Replace SQLite with Postgres migrations.
4. Improve the topic and difficulty classifier behind the rule-based first pass.
5. Add advanced math OCR for formulas that PDFs store as positioned glyphs.
