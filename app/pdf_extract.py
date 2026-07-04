import re
import zlib


def extract_pdf_text(pdf_bytes):
    pymupdf_text = _extract_with_pymupdf(pdf_bytes)
    if pymupdf_text.strip():
        return pymupdf_text
    chunks = []
    for raw_stream in _iter_streams(pdf_bytes):
        decoded = _decode_stream(raw_stream)
        if not decoded:
            continue
        text = _extract_text_operators(decoded)
        if text.strip():
            chunks.append(text)
    return "\n".join(chunks)


def _extract_with_pymupdf(pdf_bytes):
    try:
        import fitz
    except ImportError:
        return ""
    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return ""
    pages = []
    for index, page in enumerate(document, start=1):
        text = page.get_text("text", sort=True)
        if text.strip():
            pages.append(f"\n[[PAGE {index}]]\n{text}")
    return "\n".join(pages)


def _iter_streams(pdf_bytes):
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.S):
        yield match.group(1).strip(b"\r\n")


def _decode_stream(raw):
    try:
        return zlib.decompress(raw)
    except zlib.error:
        return raw


def _extract_text_operators(data):
    pieces = []
    for match in re.finditer(rb"\((?:\\.|[^\\()])*\)\s*Tj", data, re.S):
        payload = match.group(0)[1 : match.group(0).rfind(b")")]
        pieces.append(_decode_pdf_string(payload))
    for match in re.finditer(rb"\[(.*?)\]\s*TJ", data, re.S):
        strings = re.findall(rb"\((?:\\.|[^\\()])*\)", match.group(1), re.S)
        line = "".join(_decode_pdf_string(item[1:-1]) for item in strings)
        if line.strip():
            pieces.append(line)
    return "\n".join(pieces)


def _decode_pdf_string(raw):
    out = bytearray()
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == 92 and i + 1 < len(raw):
            i += 1
            esc = raw[i]
            mapping = {
                ord("n"): b"\n",
                ord("r"): b"\r",
                ord("t"): b"\t",
                ord("b"): b"\b",
                ord("f"): b"\f",
                ord("("): b"(",
                ord(")"): b")",
                ord("\\"): b"\\",
            }
            if esc in mapping:
                out.extend(mapping[esc])
            elif 48 <= esc <= 55:
                octal = bytes([esc])
                for _ in range(2):
                    if i + 1 < len(raw) and 48 <= raw[i + 1] <= 55:
                        i += 1
                        octal += bytes([raw[i]])
                    else:
                        break
                out.append(int(octal, 8))
            else:
                out.append(esc)
        else:
            out.append(ch)
        i += 1
    return out.decode("utf-8", errors="ignore")
