import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")
DEFAULT_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")


def _ollama_generate(prompt, model=DEFAULT_MODEL, timeout=90):
    endpoint = f"{DEFAULT_HOST.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }

    req = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return (data.get("response") or "").strip()
    except (URLError, TimeoutError, json.JSONDecodeError, OSError):
        return ""


def generate_resume_feedback(resume_text, job_title, job_description, job_skills, score, missing_keywords):
    resume_excerpt = (resume_text or "").strip()[:3500]
    missing_line = ", ".join((missing_keywords or [])[:15]) or "No major missing keywords detected"
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
    return _ollama_generate(prompt)


def generate_optimized_resume_with_llm(resume_text, job_title, job_description, missing_keywords):
    resume_excerpt = (resume_text or "").strip()[:5000]
    missing_line = ", ".join((missing_keywords or [])[:20]) or "No major keyword gaps"
    prompt = f"""
Rewrite the resume for ATS optimization for the role below.
Rules:
1) Keep output factual and professional.
2) Use sections: Professional Summary, Core Skills, Experience, Projects, Education.
3) Use bullet points and measurable outcomes where possible.
4) Include relevant keywords naturally, do not keyword stuff.
5) Output only the improved resume text (no markdown fences).

Target Role:
{(job_title or "").strip()}

Job Description:
{(job_description or "").strip()[:1800]}

Missing Keywords:
{missing_line}

Original Resume:
{resume_excerpt}
""".strip()
    return _ollama_generate(prompt, timeout=120)


def generate_general_resume_feedback(resume_text, score, quality_feedback):
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
