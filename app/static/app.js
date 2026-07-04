const topics = [
  "Real Numbers",
  "Polynomials",
  "Pair of Linear Equations in Two Variables",
  "Quadratic Equations",
  "Arithmetic Progressions",
  "Triangles",
  "Coordinate Geometry",
  "Introduction to Trigonometry",
  "Some Applications of Trigonometry",
  "Circles",
  "Areas Related to Circles",
  "Surface Areas and Volumes",
  "Statistics",
  "Probability",
  "Unclassified",
];

const questionTypes = [
  "MCQ",
  "Assertion-Reasoning",
  "Very Short Answer",
  "Short Answer",
  "Long Answer",
  "Case Study",
];

const topicFilter = document.querySelector("#topicFilter");
const marksFilter = document.querySelector("#marksFilter");
const sourceFilter = document.querySelector("#sourceFilter");
const searchInput = document.querySelector("#searchInput");
const questionsEl = document.querySelector("#questions");
const countLabel = document.querySelector("#countLabel");
const totalQuestions = document.querySelector("#totalQuestions");
const searchActive = document.querySelector("#searchActive");
const uploadStatus = document.querySelector("#uploadStatus");
const themeButton = document.querySelector("#themeButton");
let activeSourcePdfId = "";
let currentQuestions = [];
let availableSources = [];

applyTheme(localStorage.getItem("theme") || "dark");

for (const topic of topics) {
  const option = document.createElement("option");
  option.value = topic;
  option.textContent = topic;
  topicFilter.appendChild(option);
}

document.querySelector("#uploadForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = document.querySelector("#pdfFile").files[0];
  if (!file) {
    uploadStatus.textContent = "Choose a PDF first.";
    return;
  }
  uploadStatus.textContent = "Uploading and extracting...";
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/pdfs/upload", { method: "POST", body });
  const data = await response.json();
  if (!response.ok) {
    uploadStatus.textContent = data.error || "Upload failed.";
    return;
  }
  uploadStatus.textContent = data.duplicate
    ? "PDF already exists. Showing existing records."
    : `Extracted ${data.question_count} questions.`;
  activeSourcePdfId = data.source_pdf_id;
  sessionStorage.setItem("activeSourcePdfId", activeSourcePdfId);
  await loadSources();
  await loadQuestions();
});

document.querySelector("#refreshButton").addEventListener("click", loadQuestions);
sourceFilter.addEventListener("change", async () => {
  activeSourcePdfId = sourceFilter.value;
  await loadQuestions();
});
topicFilter.addEventListener("change", loadQuestions);
marksFilter.addEventListener("change", loadQuestions);
searchInput.addEventListener("input", () => renderQuestions(filterQuestions(currentQuestions)));
document.querySelector("#downloadJson").addEventListener("click", downloadJson);
themeButton.addEventListener("click", () => {
  const next = document.body.classList.contains("light-mode") ? "dark" : "light";
  localStorage.setItem("theme", next);
  applyTheme(next);
});

async function loadQuestions() {
  if (!activeSourcePdfId) {
    renderQuestions([]);
    return;
  }
  const params = new URLSearchParams();
  if (topicFilter.value) params.set("topic", topicFilter.value);
  if (marksFilter.value) params.set("marks", marksFilter.value);
  const response = await fetch(`/api/pdfs/${activeSourcePdfId}/questions?${params}`);
  const data = await response.json();
  currentQuestions = data.questions || [];
  renderQuestions(filterQuestions(currentQuestions));
}

async function loadSources() {
  const response = await fetch("/api/pdfs");
  const data = await response.json();
  availableSources = data.pdfs || [];
  sourceFilter.innerHTML = '<option value="">Select PDF</option>';
  for (const source of availableSources) {
    const option = document.createElement("option");
    option.value = source.id;
    option.textContent = `${source.filename} (${source.question_count || 0})`;
    sourceFilter.appendChild(option);
  }
  if (!availableSources.some((source) => source.id === activeSourcePdfId)) activeSourcePdfId = "";
  sourceFilter.value = activeSourcePdfId;
  const selected = availableSources.find((source) => source.id === activeSourcePdfId);
  uploadStatus.textContent = selected ? `Showing: ${selected.filename}` : "Select a PDF to view extracted questions.";
}

function renderQuestions(questions) {
  countLabel.textContent = `Total Questions: ${questions.length}`;
  totalQuestions.textContent = questions.length;
  searchActive.textContent = searchInput.value.trim() ? "YES" : "NO";
  questionsEl.innerHTML = "";
  if (questions.length === 0) {
    questionsEl.innerHTML = activeSourcePdfId
      ? '<div class="empty">No questions match the selected filters for this PDF.</div>'
      : '<div class="empty">Upload a CBSE Math PDF. Only that PDF questions will appear here.</div>';
    return;
  }
  for (const question of questions) {
    questionsEl.appendChild(renderQuestion(question));
  }
}

function filterQuestions(questions) {
  return questions.filter((question) => {
    if (topicFilter.value && question.topic !== topicFilter.value) return false;
    if (marksFilter.value && String(question.marks || "") !== marksFilter.value) return false;
    if (searchInput.value.trim()) {
      const haystack = `${question.question_text} ${question.topic} ${question.question_type}`.toLowerCase();
      if (!haystack.includes(searchInput.value.trim().toLowerCase())) return false;
    }
    return true;
  });
}

function renderQuestion(question) {
  const card = document.createElement("article");
  card.className = "question-card";
  const optionList = Array.isArray(question.options) && question.options.length
    ? `<div class="options">${question.options.map((option) => `<div class="option"><strong>${escapeHtml(option.label)}.</strong> ${escapeHtml(option.text)}</div>`).join("")}</div>`
    : "";
  const alternate = renderAlternateQuestion(question.alternate_question);
  const diagram = question.diagram_url && !question.diagram_url.includes("/questions/")
    ? `<figure class="diagram diagram-q${escapeHtml(question.source_qno || "")}"><img src="${escapeHtml(question.diagram_url)}" alt="Diagram for question ${escapeHtml(question.source_qno || "")}"></figure>`
    : "";
  card.innerHTML = `
    <div class="written-question">
      <div class="question-topline">
        <div class="question-number">Q${escapeHtml(question.source_qno || "")}</div>
        <div class="badges">
          <span class="badge">${escapeHtml(question.topic || "Unclassified")}</span>
          <span class="badge">${escapeHtml(question.question_type || "Type")}</span>
          ${question.has_diagram ? '<span class="badge">Diagram</span>' : ""}
        </div>
        <div class="marks-pill">${question.marks || "-"} mark${Number(question.marks) === 1 ? "" : "s"}</div>
      </div>
      <div class="question-text">${formatQuestionText(question.question_text)}</div>
      ${diagram}
      ${optionList}
      ${alternate}
    </div>
  `;
  return card;
}

function renderAlternateQuestion(alternate) {
  if (!alternate) return "";
  const optionsList = Array.isArray(alternate.options) && alternate.options.length
    ? `<div class="options alternate-options">${alternate.options.map((option) => `<div class="option"><strong>${escapeHtml(option.label)}.</strong> ${escapeHtml(option.text)}</div>`).join("")}</div>`
    : "";
  return `
    <div class="alternate-question">
      <div class="alternate-heading">${escapeHtml(alternate.heading || "Alternate question")}</div>
      <div class="question-text">${formatQuestionText(alternate.question_text || "")}</div>
      ${optionsList}
    </div>
  `;
}

function cleanDisplayText(text) {
  return String(text || "")
    .replace(/^\s*\d{1,2}[\.)]\s*/, "")
    .replace(/([a-z])\.Total/g, "$1. Total")
    .replace(/([.!?])(?:\s+[A-Z]){4,}\s*$/g, "$1")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]+/g, " ")
    .trim();
}

function formatQuestionText(text) {
  const cleaned = cleanDisplayText(text);
  const lines = cleaned.split("\n");
  const parts = [];
  let paragraph = [];
  let table = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    parts.push(`<p>${escapeHtml(paragraph.join(" "))}</p>`);
    paragraph = [];
  };
  const flushTable = () => {
    if (!table.length) return;
    const rows = normalizeTableLines(table).map((line) => {
      const cells = line.split("|").map((cell) => cell.trim()).filter(Boolean);
      return `<tr>${cells.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`;
    }).join("");
    parts.push(`<table class="extracted-table"><tbody>${rows}</tbody></table>`);
    table = [];
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      flushTable();
    } else if (line.includes("|")) {
      flushParagraph();
      table.push(line);
    } else if (/^(?:i{1,3}\.|iv\.|v\.|\([ivx]+\)|OR\b|\([A-D]\))/i.test(trimmed)) {
      flushParagraph();
      flushTable();
      parts.push(`<p class="question-line">${escapeHtml(trimmed)}</p>`);
    } else {
      flushTable();
      paragraph.push(trimmed);
    }
  }
  flushParagraph();
  flushTable();
  return parts.join("");
}

function normalizeTableLines(lines) {
  if (lines.length !== 1) return lines;
  const line = lines[0];
  if (!/Number of girls|Number of leaves|Frequency|students/i.test(line)) return lines;
  if (/Below 140/i.test(line) && /Number of girls/i.test(line)) {
    const match = line.match(/^(.*?Below 165)\s+Number of girls\s*\|\s*(.*)$/i);
    if (match) {
      return [
        match[1],
        `Number of girls | ${match[2]}`,
      ];
    }
  }
  return lines;
}

function downloadJson() {
  const payload = JSON.stringify(filterQuestions(currentQuestions), null, 2);
  const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "questions.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

function options(values, selected) {
  return values
    .map((value) => `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(value)}</option>`)
    .join("");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function applyTheme(theme) {
  const light = theme === "light";
  document.body.classList.toggle("light-mode", light);
  themeButton.textContent = light ? "Dark Mode" : "Light Mode";
}

loadSources().then(loadQuestions);
