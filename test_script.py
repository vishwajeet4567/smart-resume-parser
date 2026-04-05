from ats_engine import ats_score, build_resume_suggestions
from llm_engine import generate_optimized_resume_with_llm

resume_text = """
John Doe
Phone: 123-456-7890 | Email: john.doe@example.com

Professional Summary
Experienced software developer with a strong background in web technologies and NLP, focusing on high-quality delivery and collaboration.

Experience
Software Engineer at Tech Corp (2020 - 2023)
- Developed scalable web applications using React.
- Implemented backend logic using Python and Flask.
- Increased system performance by 25%.

Core Skills
Languages: Python, JavaScript
Frameworks/Libraries: React, Flask, scikit-learn, spacy

Education
B.S. in Computer Science - University of Technology, 2019
"""

job_title = "Senior Python Developer"
job_description = "Looking for an experienced software developer to build scalable web applications. Must know Python, React, and NLP tools."
job_skills = "Python, scikit-learn, spacy, React"

print("--- Testing ATS Engine ---")
score, missing = ats_score(resume_text, job_description, job_skills)
print(f"ATS Score: {score}%")
print(f"Missing Keywords: {missing}")

print("\\n--- Testing LLM Engine ---")
print("Waiting for Ollama response...")
improved_text = generate_optimized_resume_with_llm(resume_text, job_title, job_description, missing)
print("LLM Response:\\n", improved_text)

print("\\n--- Testing ATS Engine on Improved Text ---")
score2, missing2 = ats_score(improved_text, job_description, job_skills)
print(f"New ATS Score: {score2}%")
