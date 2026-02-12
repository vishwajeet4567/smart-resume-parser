import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _normalize_words(text):
    return re.findall(r"[a-zA-Z][a-zA-Z0-9+#\-.]*", (text or "").lower())


def ats_score(resume_text, job_text):
    resume_text = resume_text or ""
    job_text = job_text or ""
    texts = [resume_text, job_text]

    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf = vectorizer.fit_transform(texts)

    score = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
    percent = round(score * 100, 2)

    resume_words = set(_normalize_words(resume_text))
    job_words = set(_normalize_words(job_text))
    missing = sorted(job_words - resume_words, key=len, reverse=True)

    return percent, missing[:20]


def build_resume_suggestions(resume_text, job_text, missing_keywords):
    suggestions = []
    resume_text = resume_text or ""
    resume_lower = resume_text.lower()
    missing_keywords = missing_keywords or []

    top_missing = [w for w in missing_keywords if len(w) > 3][:8]
    if top_missing:
        suggestions.append(
            "Include these missing job keywords naturally in your experience/projects: "
            + ", ".join(top_missing)
            + "."
        )

    if "project" not in resume_lower:
        suggestions.append("Add a Projects section with measurable impact and relevant tools.")
    if "experience" not in resume_lower:
        suggestions.append("Add an Experience section with role, company, and quantified outcomes.")
    if "skill" not in resume_lower:
        suggestions.append("Add a Skills section grouped by technical categories.")
    if "summary" not in resume_lower and "objective" not in resume_lower:
        suggestions.append("Add a short professional summary aligned with the target role.")

    bullet_count = resume_text.count("- ") + resume_text.count("•")
    if bullet_count < 4:
        suggestions.append("Use bullet points for achievements; start with action verbs.")

    numeric_hits = re.findall(r"\d+%|\d+\+|\$\d+|\d+ users|\d+ clients", resume_text.lower())
    if len(numeric_hits) < 2:
        suggestions.append("Add quantified outcomes (e.g., 30% faster, reduced cost by 15%).")

    if len(suggestions) < 4:
        suggestions.append("Mirror the exact terminology used in the job description where accurate.")

    return suggestions[:8]


def generate_optimized_resume(resume_text, job_title, job_description, missing_keywords):
    resume_text = (resume_text or "").strip()
    job_title = (job_title or "Target Role").strip()
    job_description = (job_description or "").strip()
    missing_keywords = missing_keywords or []

    keyword_line = ", ".join(missing_keywords[:12]) if missing_keywords else "Role-specific keywords"
    job_excerpt = " ".join(job_description.split()[:140])

    improved = f"""Professional Summary
Results-focused candidate targeting {job_title}. Strong foundation in problem solving, execution, and collaboration with emphasis on delivery quality and measurable outcomes. Profile tuned for ATS relevance and recruiter readability.

Core Skills
{keyword_line}

Experience Highlights
- Delivered production-ready work aligned with business goals and quality standards.
- Improved workflow efficiency through automation, structured debugging, and clean handoffs.
- Collaborated with cross-functional stakeholders to ship requirements on schedule.
- Documented implementation details and maintained reliable support for deployed features.

Projects
- Built role-aligned projects using practical tools and measurable outcomes.
- Applied data-driven decision making and iterative testing to improve performance.
- Integrated user feedback and continuously refined deliverables.

Education
- Include degree, institution, graduation year, and relevant coursework/certifications.

Target Job Alignment Notes
{job_excerpt}
"""

    if resume_text:
        improved += (
            "\nOriginal Resume Reference\n"
            "(Use this section to preserve verified facts while adapting wording for ATS)\n"
            f"{resume_text[:1500]}"
        )

    return improved.strip()


def resume_quality_score(resume_text):
    text = (resume_text or "").strip()
    if not text:
        return 0.0, ["Resume text is empty. Upload a readable PDF or DOCX."]

    lower = text.lower()
    score = 30.0
    feedback = []

    has_contact = bool(re.search(r"@|\+?\d[\d\-\s]{7,}", text))
    if has_contact:
        score += 10
    else:
        feedback.append("Add contact details (email and phone).")

    if "summary" in lower or "objective" in lower:
        score += 8
    else:
        feedback.append("Add a short professional summary.")

    if "experience" in lower:
        score += 12
    else:
        feedback.append("Add an Experience section with role and impact.")

    if "skill" in lower:
        score += 10
    else:
        feedback.append("Add a Skills section with relevant tools and technologies.")

    if "education" in lower:
        score += 8
    else:
        feedback.append("Add an Education section.")

    bullet_count = text.count("- ") + text.count("•")
    if bullet_count >= 4:
        score += 10
    else:
        feedback.append("Use bullet points for achievements and responsibilities.")

    numeric_hits = re.findall(r"\d+%|\d+\+|\$\d+|\d+ users|\d+ clients|\d+ years", lower)
    if len(numeric_hits) >= 2:
        score += 12
    else:
        feedback.append("Include quantified outcomes (e.g., increased X by 25%).")

    if len(text.split()) >= 180:
        score += 10
    else:
        feedback.append("Expand resume content with relevant projects and outcomes.")

    score = round(min(score, 100), 2)
    if not feedback:
        feedback.append("Strong ATS baseline. Keep tailoring for each job role.")
    return score, feedback[:8]
