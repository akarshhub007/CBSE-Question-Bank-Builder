import json
import os
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pdf_questions import extract_questions_from_pdf
from app.storage import (
    ASSET_DIR,
    create_source_pdf,
    get_question,
    get_source,
    init_db,
    insert_questions,
    list_questions,
    list_sources,
    update_question,
    update_source_status,
    verify_question,
)


STATIC_DIR = ROOT / "app" / "static"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self._send_file(STATIC_DIR / "index.html", "text/html")
        if parsed.path.startswith("/static/"):
            return self._send_static(parsed.path)
        if parsed.path.startswith("/assets/"):
            return self._send_asset(parsed.path)
        if parsed.path.startswith("/api/pdfs/") and parsed.path.endswith("/status"):
            source_id = parsed.path.split("/")[3]
            source = get_source(source_id)
            return self._json(source or {"error": "Not found"}, HTTPStatus.OK if source else HTTPStatus.NOT_FOUND)
        if parsed.path.startswith("/api/pdfs/") and parsed.path.endswith("/questions"):
            source_id = parsed.path.split("/")[3]
            query = {key: values[0] for key, values in parse_qs(parsed.query).items() if values and values[0]}
            query["source_pdf_id"] = source_id
            return self._json({"questions": list_questions(query)})
        if parsed.path == "/api/pdfs":
            return self._json({"pdfs": list_sources()})
        if parsed.path == "/api/questions":
            query = {key: values[0] for key, values in parse_qs(parsed.query).items() if values and values[0]}
            return self._json({"questions": list_questions(query)})
        question_match = re.fullmatch(r"/api/questions/([^/]+)", parsed.path)
        if question_match:
            question = get_question(question_match.group(1))
            return self._json(question or {"error": "Not found"}, HTTPStatus.OK if question else HTTPStatus.NOT_FOUND)
        return self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/pdfs/upload":
            return self._handle_upload()
        verify_match = re.fullmatch(r"/api/questions/([^/]+)/verify", parsed.path)
        if verify_match:
            question = verify_question(verify_match.group(1))
            return self._json(question or {"error": "Not found"}, HTTPStatus.OK if question else HTTPStatus.NOT_FOUND)
        return self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_PATCH(self):
        match = re.fullmatch(r"/api/questions/([^/]+)", urlparse(self.path).path)
        if not match:
            return self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        payload = self._read_json()
        question = update_question(match.group(1), payload)
        return self._json(question or {"error": "Not found"}, HTTPStatus.OK if question else HTTPStatus.NOT_FOUND)

    def _handle_upload(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            return self._json({"error": "Expected multipart/form-data"}, HTTPStatus.BAD_REQUEST)
        boundary_match = re.search(r"boundary=(.+)", content_type)
        if not boundary_match:
            return self._json({"error": "Missing multipart boundary"}, HTTPStatus.BAD_REQUEST)
        length = int(self.headers.get("Content-Length", "0"))
        if length > 50 * 1024 * 1024:
            return self._json({"error": "PDF must be 50 MB or smaller"}, HTTPStatus.BAD_REQUEST)
        body = self.rfile.read(length)
        upload = _parse_multipart_file(body, boundary_match.group(1).encode())
        if not upload:
            return self._json({"error": "No file field found"}, HTTPStatus.BAD_REQUEST)
        filename, content = upload
        if not filename.lower().endswith(".pdf") or not content.startswith(b"%PDF"):
            return self._json({"error": "Only PDF files are supported"}, HTTPStatus.BAD_REQUEST)
        source, is_new = create_source_pdf(filename, content)
        if not is_new:
            return self._json({"source_pdf_id": source["id"], "status": source["processing_status"], "duplicate": True})
        try:
            update_source_status(source["id"], "processing")
            questions = extract_questions_from_pdf(content, source["id"])
            insert_questions(source["id"], questions)
            update_source_status(source["id"], "done")
            return self._json(
                {
                    "source_pdf_id": source["id"],
                    "status": "done",
                    "question_count": len(questions),
                    "duplicate": False,
                },
                HTTPStatus.CREATED,
            )
        except Exception as exc:
            update_source_status(source["id"], "failed", str(exc))
            return self._json({"source_pdf_id": source["id"], "status": "failed", "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _send_static(self, path):
        file_path = STATIC_DIR / path.removeprefix("/static/")
        content_type = "text/plain"
        if file_path.suffix == ".css":
            content_type = "text/css"
        elif file_path.suffix == ".js":
            content_type = "application/javascript"
        return self._send_file(file_path, content_type)

    def _send_asset(self, path):
        file_path = ASSET_DIR / path.removeprefix("/assets/")
        content_type = "application/octet-stream"
        if file_path.suffix.lower() == ".png":
            content_type = "image/png"
        elif file_path.suffix.lower() in {".jpg", ".jpeg"}:
            content_type = "image/jpeg"
        return self._send_file(file_path, content_type)

    def _send_file(self, file_path, content_type):
        if not file_path.exists():
            return self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _json(self, payload, status=HTTPStatus.OK):
        content = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")


def _parse_multipart_file(body, boundary):
    marker = b"--" + boundary
    for part in body.split(marker):
        if b"Content-Disposition" not in part:
            continue
        header, _, content = part.partition(b"\r\n\r\n")
        disposition = header.decode("utf-8", errors="ignore")
        if 'name="file"' not in disposition:
            continue
        filename_match = re.search(r'filename="([^"]+)"', disposition)
        if not filename_match:
            continue
        return filename_match.group(1), content.rstrip(b"\r\n-")
    return None


def main():
    init_db()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    if "PORT" in os.environ and "HOST" not in os.environ:
        host = "0.0.0.0"
    server = ThreadingHTTPServer((host, port), Handler)
    display_host = "127.0.0.1" if host == "0.0.0.0" else host
    print(f"CBSE Question Bank Builder running at http://{display_host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
