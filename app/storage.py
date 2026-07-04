import hashlib
import json
import sqlite3
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
ASSET_DIR = DATA_DIR / "assets"
DB_PATH = DATA_DIR / "question_bank.sqlite3"


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(exist_ok=True)
    ASSET_DIR.mkdir(exist_ok=True)
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_pdfs (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                storage_url TEXT NOT NULL,
                file_hash TEXT NOT NULL UNIQUE,
                uploaded_by TEXT,
                uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                total_pages INTEGER,
                processing_status TEXT NOT NULL,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                source_pdf_id TEXT NOT NULL REFERENCES source_pdfs(id),
                parent_id TEXT REFERENCES questions(id),
                question_text TEXT NOT NULL,
                question_type TEXT,
                marks INTEGER,
                topic TEXT,
                sub_topic TEXT,
                difficulty TEXT,
                has_diagram INTEGER DEFAULT 0,
                diagram_url TEXT,
                has_solution INTEGER DEFAULT 0,
                solution_text TEXT,
                solution_diagram_url TEXT,
                question_image_url TEXT,
                alternate_question TEXT,
                options TEXT,
                correct_option TEXT,
                source_page INTEGER,
                source_qno TEXT,
                year INTEGER,
                paper_set TEXT,
                confidence_score REAL,
                verified INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic);
            CREATE INDEX IF NOT EXISTS idx_questions_marks ON questions(marks);
            CREATE INDEX IF NOT EXISTS idx_questions_type ON questions(question_type);
            CREATE INDEX IF NOT EXISTS idx_questions_verified ON questions(verified);
            """
        )
        _ensure_column(db, "questions", "question_image_url", "TEXT")
        _ensure_column(db, "questions", "alternate_question", "TEXT")


def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def sha256_bytes(content):
    return hashlib.sha256(content).hexdigest()


def create_source_pdf(filename, content):
    file_hash = sha256_bytes(content)
    with connect() as db:
        existing = db.execute("SELECT * FROM source_pdfs WHERE file_hash = ?", (file_hash,)).fetchone()
        if existing:
            return dict(existing), False
        source_id = str(uuid.uuid4())
        safe_name = f"{source_id}_{Path(filename).name}"
        storage_path = UPLOAD_DIR / safe_name
        storage_path.write_bytes(content)
        db.execute(
            """
            INSERT INTO source_pdfs (id, filename, storage_url, file_hash, processing_status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source_id, filename, str(storage_path), file_hash, "pending"),
        )
        row = db.execute("SELECT * FROM source_pdfs WHERE id = ?", (source_id,)).fetchone()
        return dict(row), True


def update_source_status(source_id, status, error_message=None):
    with connect() as db:
        db.execute(
            "UPDATE source_pdfs SET processing_status = ?, error_message = ? WHERE id = ?",
            (status, error_message, source_id),
        )


def insert_questions(source_id, questions):
    with connect() as db:
        db.execute("DELETE FROM questions WHERE source_pdf_id = ?", (source_id,))
        for question in questions:
            db.execute(
                """
                INSERT INTO questions (
                    id, source_pdf_id, question_text, question_type, marks, topic, sub_topic,
                    difficulty, has_diagram, diagram_url, has_solution, solution_text,
                    solution_diagram_url, question_image_url, alternate_question, options, correct_option, source_page, source_qno,
                    confidence_score, verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    source_id,
                    question["question_text"],
                    question["question_type"],
                    question["marks"],
                    question["topic"],
                    question["sub_topic"],
                    question["difficulty"],
                    int(question["has_diagram"]),
                    question["diagram_url"],
                    int(question["has_solution"]),
                    question["solution_text"],
                    question["solution_diagram_url"],
                    question.get("question_image_url"),
                    json.dumps(question.get("alternate_question")) if question.get("alternate_question") else None,
                    json.dumps(question["options"]),
                    question["correct_option"],
                    question["source_page"],
                    question["source_qno"],
                    question["confidence_score"],
                    0,
                ),
            )


def get_source(source_id):
    with connect() as db:
        row = db.execute("SELECT * FROM source_pdfs WHERE id = ?", (source_id,)).fetchone()
        return dict(row) if row else None


def list_sources():
    with connect() as db:
        rows = db.execute(
            """
            SELECT
                source_pdfs.*,
                COUNT(questions.id) AS question_count
            FROM source_pdfs
            LEFT JOIN questions ON questions.source_pdf_id = source_pdfs.id
            GROUP BY source_pdfs.id
            ORDER BY uploaded_at DESC, filename ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def list_questions(filters=None):
    filters = filters or {}
    clauses = []
    params = []
    if filters.get("source_pdf_id"):
        clauses.append("source_pdf_id = ?")
        params.append(filters["source_pdf_id"])
    if filters.get("topic"):
        clauses.append("topic = ?")
        params.append(filters["topic"])
    if filters.get("marks"):
        clauses.append("marks = ?")
        params.append(int(filters["marks"]))
    if filters.get("type"):
        clauses.append("question_type = ?")
        params.append(filters["type"])
    if filters.get("verified") in {"true", "false", "0", "1"}:
        clauses.append("verified = ?")
        params.append(1 if filters["verified"] in {"true", "1"} else 0)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as db:
        rows = db.execute(
            f"""
            SELECT * FROM questions
            {where}
            ORDER BY CAST(source_qno AS INTEGER), source_page, created_at
            """,
            params,
        ).fetchall()
        return [_question_from_row(row) for row in rows]


def get_question(question_id):
    with connect() as db:
        row = db.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        return _question_from_row(row) if row else None


def update_question(question_id, payload):
    allowed = {
        "question_text",
        "question_type",
        "marks",
        "topic",
        "sub_topic",
        "difficulty",
        "has_diagram",
        "diagram_url",
        "has_solution",
        "solution_text",
        "solution_diagram_url",
        "question_image_url",
        "alternate_question",
        "options",
        "correct_option",
        "source_page",
        "source_qno",
        "year",
        "paper_set",
        "confidence_score",
        "verified",
    }
    updates = {key: value for key, value in payload.items() if key in allowed}
    if not updates:
        return get_question(question_id)
    if "options" in updates and not isinstance(updates["options"], str):
        updates["options"] = json.dumps(updates["options"])
    for key in ("has_diagram", "has_solution", "verified"):
        if key in updates:
            updates[key] = int(bool(updates[key]))
    updates["updated_at"] = "CURRENT_TIMESTAMP"
    columns = []
    params = []
    for key, value in updates.items():
        if key == "updated_at":
            columns.append("updated_at = CURRENT_TIMESTAMP")
        else:
            columns.append(f"{key} = ?")
            params.append(value)
    params.append(question_id)
    with connect() as db:
        db.execute(f"UPDATE questions SET {', '.join(columns)} WHERE id = ?", params)
    return get_question(question_id)


def verify_question(question_id):
    return update_question(question_id, {"verified": True})


def _question_from_row(row):
    if not row:
        return None
    data = dict(row)
    data["has_diagram"] = bool(data["has_diagram"])
    data["has_solution"] = bool(data["has_solution"])
    data["verified"] = bool(data["verified"])
    try:
        data["options"] = json.loads(data["options"] or "[]")
    except json.JSONDecodeError:
        data["options"] = []
    try:
        data["alternate_question"] = json.loads(data["alternate_question"]) if data.get("alternate_question") else None
    except json.JSONDecodeError:
        data["alternate_question"] = None
    data.pop("question_image_url", None)
    return data


def _ensure_column(db, table, column, definition):
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
