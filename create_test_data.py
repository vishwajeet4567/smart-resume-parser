import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("database.db", timeout=10)
cur = conn.cursor()

# Create Recruiter
email = "test.recruiter@example.com"
password = generate_password_hash("password123")
try:
    cur.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)", ("Test Recruiter", email, password, "recruiter"))
except sqlite3.IntegrityError:
    pass # Already exists

# Create Job
title = "Senior Python/React Developer"
desc = "Looking for a seasoned software developer with a strong background in web technologies. You will be responsible for building scalable web applications. The ideal candidate has experience with NLP tools and full-stack development."
skills = "Python, React, Flask, scikit-learn, spacy"
cur.execute("INSERT INTO jobs(title, description, skills, recruiter_email) VALUES(?,?,?,?)", (title, desc, skills, email))

conn.commit()
conn.close()
print("Recruiter and Test Job created successfully!")
