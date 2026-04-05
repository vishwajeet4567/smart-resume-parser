import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen

# Define the local AI model we want to use. We are using gemma3:1b because it runs fast locally.
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")
# Define the local address where the Ollama server is running (usually port 11434)
DEFAULT_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")


def _ollama_generate(prompt, model=DEFAULT_MODEL, timeout=90):
    """
    This is the core helper function that actually sends the text to the local AI server.
    It builds a web request, sends the prompt to the Ollama API, and waits for a response.
    """
    endpoint = f"{DEFAULT_HOST.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,  # We want the whole response at once, not streamed word-by-word
        "options": {"temperature": 0.2}, # Low temperature makes the AI more factual and less creative/random
    }

    # Prepare the HTTP request
    req = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        # Send the request and wait for the AI to finish thinking (up to 'timeout' seconds)
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return (data.get("response") or "").strip()
    except (URLError, TimeoutError, json.JSONDecodeError, OSError):
        # If the Ollama server is off or crashes, return an empty string instead of breaking the app
        return ""


def generate_resume_feedback(resume_text, job_title, job_description, job_skills, score, missing_keywords):
    """
    Asks the AI to generate 5 specific tips on how the student can improve their resume
    for a specific job. This is used on the "Upload & Compare" page.
    """
    # Chop off the resume if it's too long so we don't overwhelm the AI's memory limits
    resume_excerpt = (resume_text or "").strip()[:3500]
    missing_line = ", ".join((missing_keywords or [])[:15]) or "No major missing keywords detected"
    
    # This is the strict instruction template we send to the AI
    prompt = f"""
You are an ATS resume coach. Give concise feedback based on the resume and target role.
Return plain text with exactly 5 bullet points.
Each bullet must be practical and specific.

Target Job Title:
{(job_title or "").strip()}

Target Job Description:
{(job_description or "").strip()[:1500]}

Target Job Skills:
{(job_skills or "").strip()[:600]}

Current ATS Score:
{score}%

Missing Keywords:
{missing_line}

Resume:
{resume_excerpt}
""".strip()
    # Send the prompt to our helper function
    return _ollama_generate(prompt)


def generate_optimized_resume_with_llm(resume_text, job_title, job_description, missing_keywords):
    """
    The big feature: Asks the AI to read the student's resume, read the job description,
    and then completely rewrite the resume to ensure the missing keywords are included
    and it sounds professional. Used when they click "Improve Resume".
    """
    resume_excerpt = (resume_text or "").strip()[:5000]
    missing_line = ", ".join((missing_keywords or [])[:20]) or "No major keyword gaps"
    prompt = f"""
You are an expert Technical Recruiter and ATS Optimization Specialist.
Your task is to rewrite the candidate's resume to max out the ATS score for the target role, while remaining entirely factual based on the original resume.

Target Role:
{(job_title or "").strip()}

Job Description:
{(job_description or "").strip()[:1800]}

Missing Critical Keywords:
{missing_line}

Original Resume:
{resume_excerpt}

Rules for the rewrite:
1) Act as a strict recruiter: remove fluff, focus on impact and metrics.
2) Ensure all "Missing Critical Keywords" are seamlessly and naturally integrated into the Experience or Skills sections. Do not just list them awkwardly.
3) Use the exact structure: Professional Summary, Core Skills, Experience, Projects, Education.
4) Start all experience bullets with strong action verbs. Ensure bullets follow the "Accomplished [X] as measured by [Y], by doing [Z]" format where possible.
5) Output ONLY the finalized, improved resume text. Do not include introductory conversational text or markdown fences like ```.
""".strip()
    # Give the AI more time (120s) because rewriting a whole resume takes a while
    return _ollama_generate(prompt, timeout=120)


def generate_general_resume_feedback(resume_text, score, quality_feedback):
    """
    Asks the AI to generate 5 tips for general resume improvement BEFORE they even apply to a job.
    Used on the "General Resume Check" page. It bases its advice on the rule-based NLP score.
    """
    resume_excerpt = (resume_text or "").strip()[:3500]
    checks_line = ", ".join((quality_feedback or [])[:8]) or "No major quality issues detected"
    prompt = f"""
You are an ATS resume reviewer.
Provide exactly 5 concise bullet points to improve this resume for ATS quality.
Avoid job-specific advice; keep it general and practical.

Current Resume ATS Quality Score:
{score}%

Current Quality Notes:
{checks_line}

Resume:
{resume_excerpt}
""".strip()
    return _ollama_generate(prompt)
