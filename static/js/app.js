function initJobFilter() {
  const search = document.getElementById("jobSearch");
  const jobsList = document.getElementById("jobsList");
  const count = document.getElementById("jobCount");
  if (!search || !jobsList || !count) return;

  const cards = Array.from(jobsList.querySelectorAll(".job-card"));
  const total = cards.length;

  search.addEventListener("input", () => {
    const q = search.value.trim().toLowerCase();
    let visible = 0;

    cards.forEach((card) => {
      const haystack = `${card.dataset.title} ${card.dataset.desc} ${card.dataset.skills}`;
      const match = haystack.includes(q);
      card.style.display = match ? "block" : "none";
      if (match) visible += 1;
    });

    count.textContent = `${visible} of ${total} jobs`;
  });
}

function initCopySkills() {
  document.querySelectorAll(".copy-skills-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const skills = btn.dataset.skills || "";
      try {
        await navigator.clipboard.writeText(skills);
        btn.textContent = "Copied";
        setTimeout(() => {
          btn.textContent = "Copy Skills";
        }, 1200);
      } catch (e) {
        btn.textContent = "Cannot Copy";
      }
    });
  });
}

function initScoreRing() {
  const ring = document.querySelector(".score-ring");
  if (!ring) return;

  const target = Number(ring.dataset.score || 0);
  let current = 0;
  const timer = setInterval(() => {
    current += 2;
    if (current >= target) {
      current = target;
      clearInterval(timer);
    }
    ring.style.setProperty("--value", String(current));
  }, 16);
}

function initDescriptionCounter() {
  const desc = document.getElementById("description");
  const counter = document.getElementById("descCounter");
  if (!desc || !counter) return;

  const update = () => {
    counter.textContent = `${desc.value.length} characters`;
  };
  desc.addEventListener("input", update);
  update();
}

function cleanFeedbackText(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/`(.*?)`/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

function extractFeedbackPoints(rawText) {
  const mainPart = rawText.split(/\n\s*-{3,}\s*\n/)[0];
  const points = [];
  const bulletPattern = /(?:^|\n)\s*(?:[-*]|\d+\.)\s+([\s\S]*?)(?=\n\s*(?:[-*]|\d+\.)\s+|$)/g;
  let match;

  while ((match = bulletPattern.exec(mainPart)) !== null) {
    const cleaned = cleanFeedbackText(match[1]);
    if (cleaned.length >= 18) {
      points.push(cleaned);
    }
  }

  if (points.length) return points;

  return mainPart
    .split(/\n{2,}/)
    .map((block) => cleanFeedbackText(block))
    .filter((block) => block.length >= 30)
    .slice(0, 6);
}

function splitFeedbackTitle(point, idx) {
  const withLabel = point.match(/^([^:.!?]{8,90})(:|-)\s+(.+)$/);
  if (withLabel) {
    return { title: withLabel[1].trim(), body: withLabel[3].trim() };
  }

  const firstSentence = point.match(/^(.{16,120}?[.!?])\s+(.+)$/);
  if (firstSentence) {
    return { title: firstSentence[1].trim(), body: firstSentence[2].trim() };
  }

  return { title: `Recommendation ${idx + 1}`, body: point };
}

function classifyFeedback(point) {
  const text = point.toLowerCase();
  const rules = [
    {
      key: "keywords",
      label: "Keywords",
      pattern: /\b(keyword|skills?|tech stack|python|java|sql|flask|django|api)\b/,
    },
    {
      key: "formatting",
      label: "Formatting",
      pattern: /\b(format|layout|section|heading|bullet|readability|ats[- ]friendly)\b/,
    },
    {
      key: "impact",
      label: "Impact",
      pattern: /\b(impact|quantif|metric|result|achievement|improved|increased|reduced)\b/,
    },
    {
      key: "relevance",
      label: "Relevance",
      pattern: /\b(tailor|relevant|target role|job description|alignment|fit)\b/,
    },
    {
      key: "experience",
      label: "Experience",
      pattern: /\b(experience|project|responsibilit|internship|work history)\b/,
    },
  ];

  const match = rules.find((rule) => rule.pattern.test(text));
  return match || { key: "general", label: "General" };
}

function initLlmFeedbackCards() {
  const widgets = document.querySelectorAll(".llm-feedback-widget");
  if (!widgets.length) return;

  widgets.forEach((widget) => {
    const rawEl = widget.querySelector(".llm-feedback-raw");
    const grid = widget.querySelector(".feedback-grid");
    const countEl = widget.querySelector(".feedback-count");
    if (!rawEl || !grid || !countEl) return;

    const points = extractFeedbackPoints(rawEl.textContent || "");
    if (!points.length) {
      countEl.textContent = "0 tips";
      return;
    }

    countEl.textContent = `${points.length} tips`;

    points.forEach((point, idx) => {
      const formatted = splitFeedbackTitle(point, idx);
      const category = classifyFeedback(point);
      const item = document.createElement("details");
      item.className = "feedback-item";
      item.dataset.category = category.key;
      if (idx < 2) item.open = true;

      const summary = document.createElement("summary");

      const chip = document.createElement("span");
      chip.className = "feedback-chip";
      chip.textContent = category.label;

      const tipNo = document.createElement("span");
      tipNo.className = "feedback-tipno";
      tipNo.textContent = `Tip ${idx + 1}`;

      const title = document.createElement("span");
      title.className = "feedback-title";
      title.textContent = formatted.title;

      const body = document.createElement("p");
      body.textContent = formatted.body;

      summary.appendChild(chip);
      summary.appendChild(tipNo);
      summary.appendChild(title);
      item.appendChild(summary);
      item.appendChild(body);
      grid.appendChild(item);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initJobFilter();
  initCopySkills();
  initScoreRing();
  initDescriptionCounter();
  initLlmFeedbackCards();
});

