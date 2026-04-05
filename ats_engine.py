import re
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Step 1: Attempt to load the advanced English Language model (spaCy)
# This model lets us recognize that words like "running" and "ran" mean the same thing ("run").
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # If the user hasn't downloaded the spaCy model, fallback to basic text processing
    nlp = None


def _normalize_words_spacy(text):
    """
    Cleans up the text by removing punctuation, stop words (like 'and', 'the'), 
    and converts every word into its base form (lemma).
    """
    if not text:
        return []
    
    # Make everything lowercase so "Python" matches "python"
    text = text.lower()
    
    # Fallback if spaCy failed to load: just grab any sequence of letters and basic symbols using simple regex
    if nlp is None:
        return re.findall(r"[a-zA-Z][a-zA-Z0-9+#\-.]*", text)
        
    # Process the text through the NLP engine
    doc = nlp(text)
    
    # Extract the base form (lemma) of every word, skipping punctuation, spaces, and useless stop words
    words = [token.lemma_ for token in doc if not token.is_stop and not token.is_punct and not token.is_space and bool(re.match(r"^[a-z0-9+#\-.]+$", token.lemma_))]
    return words


def ats_score(resume_text, job_text, job_skills=""):
    """
    The main algorithm to check how well a resume matches a specific job.
    Returns:
    1. A percentage match score (0 to 100)
    2. A list of up to 20 important keywords the applicant missed.
    """
    resume_text = resume_text or ""
    job_text = job_text or ""
    job_skills = job_skills or ""
    
    # --- PHASE 1: Base Frequency Score (TF-IDF) ---
    # This measures how frequently important words from the Job Description appear in the Resume.
    texts = [resume_text, job_text]
    vectorizer = TfidfVectorizer(stop_words="english")
    try:
        tfidf = vectorizer.fit_transform(texts)
        # Calculate the mathematical similarity between the two texts
        base_score = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
    except ValueError:
        # Handles edge cases where one of the texts is completely empty
        base_score = 0.0 
        
    # --- PHASE 2: Core Skill Multiplier Boost ---
    # This phase rewards candidates significantly for matching explicitly requested "Core Skills"
    
    # Extract clean, base-form words from all three bodies of text
    resume_lemmas = set(_normalize_words_spacy(resume_text))
    job_desc_lemmas = set(_normalize_words_spacy(job_text))
    skill_words = set(_normalize_words_spacy(job_skills))
    
    # Decide what our "Target Words" are for calculating what the user missed.
    # We heavily prioritize the exact "skills" string provided by the recruiter.
    target_words = skill_words if skill_words else job_desc_lemmas
    
    # If the recruiter provided core skills, calculate the boost
    skill_boost = 0.0
    matched_skills = 0
    if skill_words:
        for skill in skill_words:
            # If a strict skill required by the job is found in the resume, add 5% to their final score!
            if skill in resume_lemmas:
                matched_skills += 1
                skill_boost += 0.05 
                
    # Combine the Frequency Score with the Skill Boost. Cap it at 1.0 (100%).
    final_score = min(1.0, base_score + skill_boost)
    percent = round(final_score * 100, 2)

    # --- PHASE 3: Identify Missing Keywords ---
    # Subtract the words the user has from the words the job wants.
    # Sort them by length (longer words are usually more specific technical terms)
    missing = sorted(target_words - resume_lemmas, key=len, reverse=True)

    # Return the final percentage, and the top 20 missing words to show the user
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
        
    # Check for Experience Duration markers (e.g. 2020 - 2023, Jan 2021 to Present)
    date_ranges = re.findall(r"(20\d{2}|\b\d{4}\b)\s*(?:-|to)\s*(20\d{2}|\b\d{4}\b|present|current)", lower)
    if len(date_ranges) >= 1:
        score += 10
    else:
        feedback.append("Include clear date ranges for your experience (e.g., 2021 - Present).")

    if len(text.split()) >= 180:
        score += 10
    else:
        feedback.append("Expand resume content with relevant projects and outcomes.")

    score = round(min(score, 100), 2)
    if not feedback:
        feedback.append("Strong ATS baseline. Keep tailoring for each job role.")
    return score, feedback[:8]
