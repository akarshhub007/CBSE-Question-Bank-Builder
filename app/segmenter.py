import re

from .classifier import classify_question


QUESTION_START = re.compile(
    r"(?im)^\s*(?:Q(?:uestion)?\.?\s*)?(?P<label>\d{1,2})(?:\s*\(([a-zivx]+)\))?[\.\)]\s+"
)


def segment_questions(text):
    clean = normalize_text(text)
    clean = _trim_to_questions(clean)
    matches = list(QUESTION_START.finditer(clean))
    if not matches:
        return []
    questions = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(clean)
        label = match.group("label").replace(" ", "")
        body = clean[match.end() : end].strip()
        body = clean_question_text(body)
        if _looks_like_instruction(body):
            continue
        if len(body) < 10:
            continue
        metadata = classify_question(body, section_marks=_section_marks_before(clean, start))
        questions.append(
            {
                "source_qno": label,
                "question_text": body,
                "source_page": 1,
                "has_diagram": False,
                "diagram_url": None,
                "has_solution": False,
                "solution_text": None,
                "solution_diagram_url": None,
                "correct_option": None,
                **metadata,
            }
        )
    return questions


def normalize_text(text):
    text = text.replace("\x00", "")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*-\s*\n", "-", text)
    text = re.sub(r"(?<=\w)\n(?=\w)", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_question_text(text):
    text = re.sub(r"\[\[PAGE\s+\d+\]\]", "", text)
    text = re.sub(r"\bPage\s+\d+\s+of\s+\d+\b", "", text, flags=re.I)
    text = re.sub(r"(?<=\S)\s+[1-5]\s*(?=\n)", "", text)
    text = re.sub(r"\b\d+\s*$", "", text.strip())
    text = re.sub(r"\n\s*([A-Da-d])\s*[\).]\s*", lambda m: f"\n({m.group(1).upper()}) ", text)
    text = re.sub(r"(?<!\n)\s+\(([A-Da-d])\)\s+", lambda m: f"\n({m.group(1).upper()}) ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _trim_to_questions(text):
    markers = [
        r"(?im)^\s*Q\.?\s*No\.?\s*$\s*^\s*Questions?\s*$",
        r"(?im)^\s*Section\s+A\s+consists\s+of\s+\d+\s+questions?",
        r"(?im)^\s*SECTION\s+A\s*$",
    ]
    starts = []
    for pattern in markers:
        match = re.search(pattern, text)
        if match:
            starts.append(match.end())
    if starts:
        section_text = text[min(starts) :]
        first_question = QUESTION_START.search(section_text)
        if first_question:
            return section_text[first_question.start() :]
        return section_text
    return text


def _looks_like_instruction(text):
    lowered = " ".join(text.lower().split())
    instruction_bits = [
        "this question paper contains",
        "all questions are compulsory",
        "question paper is divided",
        "there is no overall choice",
        "draw neat and clean figures",
        "use of calculators",
    ]
    return any(bit in lowered for bit in instruction_bits)


def _section_marks_before(text, position):
    window = text[max(0, position - 600) : position].lower()
    match = re.search(r"section\s+[a-z].{0,80}?(\d)\s*marks?\s+each", window, re.S)
    if match:
        return int(match.group(1))
    return None
