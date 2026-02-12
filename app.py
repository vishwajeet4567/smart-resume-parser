from flask import Flask, render_template, request, redirect, session, flash
import json
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from resume_parser import extract_resume_text
from ats_engine import ats_score, build_resume_suggestions, generate_optimized_resume

app = Flask(__name__)
app.secret_key = "secret123"
os.makedirs("uploads", exist_ok=True)

def init_db():
    conn = sqlite3.connect("database.db", timeout=10)
    cur = conn.cursor()

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """
    )

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS jobs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        skills TEXT,
        recruiter_email TEXT
    )
    """
    )

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS applications(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_email TEXT,
        job_id INTEGER,
        resume_filename TEXT,
        score REAL,
        missing_keywords TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """
    )

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS student_profiles(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_email TEXT UNIQUE,
        full_name TEXT,
        phone TEXT,
        location TEXT,
        linkedin TEXT,
        portfolio TEXT,
        skills TEXT,
        about TEXT
    )
    """
    )

    conn.commit()
    conn.close()


init_db()


def get_db_connection():
    conn = sqlite3.connect("database.db", timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def role_required(role):
    return "user" in session and session.get("role") == role


def get_or_create_student_profile(email, default_name=""):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM student_profiles WHERE student_email=?", (email,))
    profile = cur.fetchone()
    if not profile:
        cur.execute(
            """
            INSERT INTO student_profiles(student_email, full_name)
            VALUES(?, ?)
            """,
            (email, default_name),
        )
        conn.commit()
        cur.execute("SELECT * FROM student_profiles WHERE student_email=?", (email,))
        profile = cur.fetchone()
    conn.close()
    return profile


@app.context_processor
def inject_user_context():
    return {
        "is_logged_in": "user" in session,
        "user_email": session.get("user"),
        "role": session.get("role"),
    }


# ---------- ROUTES ----------
@app.route("/upload_resume", methods=["GET", "POST"])
def upload_resume():
    if not role_required("student"):
        flash("Please log in as a student to upload a resume.", "error")
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, description, skills FROM jobs ORDER BY id DESC")
    jobs = cur.fetchall()

    analysis = None
    selected_job_id = None
    stored_analysis = session.get("resume_ai_result")
    if stored_analysis:
        analysis = json.loads(stored_analysis)
        selected_job_id = analysis.get("job_id")

    if request.method == "POST":
        file = request.files["resume"]
        job_id_raw = request.form.get("job_id", "").strip()

        if not file or not file.filename:
            conn.close()
            flash("Please choose a resume file.", "error")
            return redirect("/upload_resume")

        if not jobs:
            conn.close()
            flash("No jobs available. Ask recruiter to post a job first.", "error")
            return redirect("/student")

        try:
            job_id = int(job_id_raw)
        except ValueError:
            conn.close()
            flash("Please select a target job profile.", "error")
            return redirect("/upload_resume")

        target_job = next((job for job in jobs if job["id"] == job_id), None)
        if not target_job:
            conn.close()
            flash("Selected job was not found.", "error")
            return redirect("/upload_resume")

        filename = secure_filename(file.filename)
        path = os.path.join("uploads", filename)
        file.save(path)

        text = extract_resume_text(path)
        if not text.strip():
            conn.close()
            flash("Could not extract text from resume. Try another file.", "error")
            return redirect("/upload_resume")

        score, missing = ats_score(text, target_job["description"] or "")
        suggestions = build_resume_suggestions(
            text,
            f"{target_job['description'] or ''} {target_job['skills'] or ''}",
            missing,
        )

        analysis = {
            "job_id": target_job["id"],
            "job_title": target_job["title"],
            "score": score,
            "missing": missing,
            "suggestions": suggestions,
        }

        session["resume_text"] = text
        session["resume_filename"] = filename
        session["resume_ai_result"] = json.dumps(analysis)
        selected_job_id = target_job["id"]

        cur.execute(
            """
            INSERT INTO applications(student_email, job_id, resume_filename, score, missing_keywords)
            VALUES(?,?,?,?,?)
            """,
            (
                session["user"],
                target_job["id"],
                filename,
                score,
                json.dumps(missing),
            ),
        )
        conn.commit()
        conn.close()
        flash("AI/ML ATS check completed. Review suggestions below.", "success")
        return render_template(
            "upload_resume.html",
            jobs=jobs,
            analysis=analysis,
            selected_job_id=selected_job_id,
        )

    conn.close()
    return render_template(
        "upload_resume.html",
        jobs=jobs,
        analysis=analysis,
        selected_job_id=selected_job_id,
    )


@app.route("/resume/improve", methods=["POST"])
def improve_resume():
    if not role_required("student"):
        flash("Please log in as a student.", "error")
        return redirect("/")

    resume_text = session.get("resume_text")
    stored_analysis = session.get("resume_ai_result")
    if not resume_text or not stored_analysis:
        flash("Upload and analyze your resume first.", "error")
        return redirect("/upload_resume")

    analysis = json.loads(stored_analysis)
    job_id = analysis.get("job_id")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, description, skills FROM jobs WHERE id=?", (job_id,))
    job = cur.fetchone()
    conn.close()
    if not job:
        flash("Target job no longer exists.", "error")
        return redirect("/upload_resume")

    improved_text = generate_optimized_resume(
        resume_text,
        job["title"],
        f"{job['description'] or ''} {job['skills'] or ''}",
        analysis.get("missing", []),
    )
    improved_score, improved_missing = ats_score(improved_text, job["description"] or "")
    improved_suggestions = build_resume_suggestions(
        improved_text,
        f"{job['description'] or ''} {job['skills'] or ''}",
        improved_missing,
    )

    session["resume_improved_text"] = improved_text

    return render_template(
        "resume_improved.html",
        job=job,
        original_score=analysis.get("score", 0),
        improved_score=improved_score,
        improved_missing=improved_missing,
        improved_suggestions=improved_suggestions,
        improved_text=improved_text,
    )


@app.route("/resume/use-improved", methods=["POST"])
def use_improved_resume():
    if not role_required("student"):
        flash("Please log in as a student.", "error")
        return redirect("/")

    improved_text = session.get("resume_improved_text")
    if not improved_text:
        flash("No improved resume draft found.", "error")
        return redirect("/upload_resume")

    session["resume_text"] = improved_text
    session["resume_filename"] = "optimized_resume_draft.txt"
    flash("Improved resume draft is now active for ATS analysis.", "success")
    return redirect("/student/job-profile")


@app.route("/analyze")
def analyze():
    if not role_required("student"):
        flash("Please log in as a student to access ATS analysis.", "error")
        return redirect("/")

    if "resume_text" not in session:
        flash("Upload your resume first to run ATS analysis.", "error")
        return redirect("/upload_resume")

    job_id = request.args.get("job_id", type=int)

    conn = get_db_connection()
    cur = conn.cursor()
    if job_id:
        cur.execute("SELECT id, title, description, skills FROM jobs WHERE id=?", (job_id,))
    else:
        cur.execute("SELECT id, title, description, skills FROM jobs LIMIT 1")
    job = cur.fetchone()

    if not job:
        conn.close()
        flash("No jobs available for comparison yet.", "error")
        return redirect("/jobs")

    score, missing = ats_score(session["resume_text"], job["description"] or "")

    cur.execute(
        """
        INSERT INTO applications(student_email, job_id, resume_filename, score, missing_keywords)
        VALUES(?,?,?,?,?)
        """,
        (
            session["user"],
            job["id"],
            session.get("resume_filename"),
            score,
            json.dumps(missing),
        ),
    )
    conn.commit()
    conn.close()

    return render_template(
        "result.html",
        score=score,
        missing=missing,
        job=job,
        resume_filename=session.get("resume_filename"),
    )


@app.route("/")
def home():
    if role_required("recruiter"):
        return redirect("/recruiter")
    if role_required("student"):
        return redirect("/student")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        plain_password = request.form.get("password", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "student").strip()

        if not all((name, email, plain_password, role)):
            flash("All fields are required.", "error")
            return redirect("/register")

        data = (name, email, generate_password_hash(plain_password), role)

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)", data)
            conn.commit()
            conn.close()
        except sqlite3.IntegrityError:
            flash("Email is already registered.", "error")
            return redirect("/register")

        flash("Registration successful. Please log in.", "success")
        return redirect("/")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return redirect("/")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=?", (email,))
    user = cur.fetchone()

    if user:
        stored_password = user["password"] or ""
        valid_password = False

        if stored_password.startswith(("pbkdf2:", "scrypt:")):
            valid_password = check_password_hash(stored_password, password)
        else:
            # Legacy support: auto-upgrade plaintext credentials to a hash.
            valid_password = stored_password == password
            if valid_password:
                cur.execute(
                    "UPDATE users SET password=? WHERE id=?",
                    (generate_password_hash(password), user["id"]),
                )
                conn.commit()

        conn.close()

        if valid_password:
            session["user"] = user["email"]
            session["role"] = user["role"]
            session["name"] = user["name"]
            if user["role"] == "recruiter":
                return redirect("/recruiter")
            return redirect("/student")
    else:
        conn.close()

    flash("Invalid email or password.", "error")
    return redirect("/")


@app.route("/recruiter")
def recruiter_dash():
    if not role_required("recruiter"):
        flash("Recruiter access required.", "error")
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS count FROM jobs WHERE recruiter_email=?", (session["user"],))
    my_jobs = cur.fetchone()["count"]
    cur.execute("SELECT COUNT(*) AS count FROM jobs")
    total_jobs = cur.fetchone()["count"]

    cur.execute(
        """
        SELECT
            j.id,
            j.title,
            COUNT(a.id) AS applicants,
            AVG(a.score) AS avg_score
        FROM jobs j
        LEFT JOIN applications a ON a.job_id = j.id
        WHERE j.recruiter_email = ?
        GROUP BY j.id, j.title
        ORDER BY j.id DESC
        """,
        (session["user"],),
    )
    job_stats = cur.fetchall()

    cur.execute(
        """
        SELECT
            a.student_email,
            a.score,
            a.created_at,
            j.title AS job_title
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE j.recruiter_email = ?
        ORDER BY a.created_at DESC
        LIMIT 10
        """,
        (session["user"],),
    )
    recent_applications = cur.fetchall()
    conn.close()

    return render_template(
        "recruiter_dashboard.html",
        my_jobs=my_jobs,
        total_jobs=total_jobs,
        job_stats=job_stats,
        recent_applications=recent_applications,
    )


@app.route("/student")
def student_dash():
    if not role_required("student"):
        flash("Student access required.", "error")
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS count FROM jobs")
    total_jobs = cur.fetchone()["count"]
    cur.execute("SELECT * FROM jobs ORDER BY id DESC")
    all_jobs = cur.fetchall()

    cur.execute(
        """
        SELECT
            a.score,
            a.created_at,
            a.resume_filename,
            j.title AS job_title
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE a.student_email = ?
        ORDER BY a.created_at DESC
        LIMIT 8
        """,
        (session["user"],),
    )
    history = cur.fetchall()
    conn.close()

    profile = get_or_create_student_profile(session["user"], session.get("name", ""))

    return render_template(
        "student_home.html",
        total_jobs=total_jobs,
        jobs=all_jobs,
        resume_uploaded="resume_text" in session,
        resume_filename=session.get("resume_filename"),
        history=history,
        profile=profile,
    )


@app.route("/student/job-profile")
def student_job_profile():
    if not role_required("student"):
        flash("Student access required.", "error")
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs ORDER BY id DESC")
    all_jobs = cur.fetchall()
    conn.close()
    return render_template(
        "student_job_profile.html",
        jobs=all_jobs,
        resume_uploaded="resume_text" in session,
    )


@app.route("/student/jobs/<int:job_id>")
def student_job_detail(job_id):
    if not role_required("student"):
        flash("Student access required.", "error")
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
    job = cur.fetchone()
    conn.close()
    if not job:
        flash("Job not found.", "error")
        return redirect("/student/job-profile")

    return render_template(
        "student_job_detail.html",
        job=job,
        resume_uploaded="resume_text" in session,
    )


@app.route("/student/profile", methods=["GET", "POST"])
def student_profile():
    if not role_required("student"):
        flash("Student access required.", "error")
        return redirect("/")

    email = session["user"]
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        location = request.form.get("location", "").strip()
        linkedin = request.form.get("linkedin", "").strip()
        portfolio = request.form.get("portfolio", "").strip()
        skills = request.form.get("skills", "").strip()
        about = request.form.get("about", "").strip()

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM student_profiles WHERE student_email=?", (email,))
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """
                UPDATE student_profiles
                SET full_name=?, phone=?, location=?, linkedin=?, portfolio=?, skills=?, about=?
                WHERE student_email=?
                """,
                (full_name, phone, location, linkedin, portfolio, skills, about, email),
            )
        else:
            cur.execute(
                """
                INSERT INTO student_profiles(student_email, full_name, phone, location, linkedin, portfolio, skills, about)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (email, full_name, phone, location, linkedin, portfolio, skills, about),
            )
        conn.commit()
        conn.close()
        flash("Profile updated successfully.", "success")
        return redirect("/student/profile")

    profile = get_or_create_student_profile(email, session.get("name", ""))
    return render_template("student_profile.html", profile=profile)


@app.route("/student/help")
def student_help():
    if not role_required("student"):
        flash("Student access required.", "error")
        return redirect("/")
    return render_template("student_help.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect("/")


# ---------- JOB POST ----------
@app.route("/post_job", methods=["GET", "POST"])
def post_job():
    if not role_required("recruiter"):
        flash("Recruiter access required.", "error")
        return redirect("/")

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        skills = request.form.get("skills")

        if not title or not description:
            flash("Title and description are required.", "error")
            return redirect("/post_job")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
        INSERT INTO jobs(title, description, skills, recruiter_email)
        VALUES(?,?,?,?)
        """,
            (title, description, skills, session["user"]),
        )

        conn.commit()
        conn.close()

        flash("Job posted successfully.", "success")
        return redirect("/recruiter")

    return render_template("post_job.html")


@app.route("/jobs")
def jobs():
    if "user" not in session:
        flash("Please log in to view jobs.", "error")
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs ORDER BY id DESC")
    all_jobs = cur.fetchall()
    conn.close()

    return render_template("jobs.html", jobs=all_jobs, resume_uploaded="resume_text" in session)


# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)
