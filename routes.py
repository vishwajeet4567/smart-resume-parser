import json
import os
import sqlite3

from flask import flash, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from ats_engine import resume_quality_score
from auth_helpers import get_or_create_student_profile, role_required
from db import get_db_connection
from llm_engine import generate_general_resume_feedback
from resume_parser import extract_resume_text

"""
This file contains the routing logic for the application.
It appears to be part of a refactoring effort to move routes out of app.py.
Currently, app.py acts as the main entry point and contains the active routes.
"""

def register_routes(app):
    @app.route("/upload_resume", methods=["GET", "POST"])
    def upload_resume():
        if not role_required("student"):
            flash("Please log in as a student to upload a resume.", "error")
            return redirect("/")
        flash("Job-based ATS check is disabled. Use Individual ATS instead.", "error")
        return redirect("/upload_resume_individual")

    @app.route("/upload_resume_individual", methods=["GET", "POST"])
    def upload_resume_individual():
        if not role_required("student"):
            flash("Please log in as a student to upload a resume.", "error")
            return redirect("/")

        analysis = None
        stored_analysis = session.get("resume_individual_result")
        if stored_analysis:
            analysis = json.loads(stored_analysis)

        if request.method == "POST":
            file = request.files["resume"]
            if not file or not file.filename:
                flash("Please choose a resume file.", "error")
                return redirect("/upload_resume_individual")

            filename = secure_filename(file.filename)
            path = os.path.join("uploads", filename)
            file.save(path)

            text = extract_resume_text(path)
            if not text.strip():
                flash("Could not extract text from resume. Try another file.", "error")
                return redirect("/upload_resume_individual")

            score, quality_feedback = resume_quality_score(text)
            llm_feedback = generate_general_resume_feedback(text, score, quality_feedback)

            analysis = {
                "score": score,
                "quality_feedback": quality_feedback,
                "llm_feedback": llm_feedback,
                "resume_filename": filename,
            }

            session["resume_text"] = text
            session["resume_filename"] = filename
            session["resume_individual_result"] = json.dumps(analysis)

            flash("Individual ATS resume check completed.", "success")
            return render_template("upload_resume_individual.html", analysis=analysis)

        return render_template("upload_resume_individual.html", analysis=analysis)

    @app.route("/resume/improve", methods=["POST"])
    def improve_resume():
        if not role_required("student"):
            flash("Please log in as a student.", "error")
            return redirect("/")
        flash("Job-based ATS improvement is disabled. Use Individual ATS instead.", "error")
        return redirect("/upload_resume_individual")

    @app.route("/resume/use-improved", methods=["POST"])
    def use_improved_resume():
        if not role_required("student"):
            flash("Please log in as a student.", "error")
            return redirect("/")
        flash("Job-based ATS improvement is disabled. Use Individual ATS instead.", "error")
        return redirect("/upload_resume_individual")

    @app.route("/analyze")
    def analyze():
        if not role_required("student"):
            flash("Please log in as a student to access ATS analysis.", "error")
            return redirect("/")
        flash("Job-based ATS analysis is disabled. Use Individual ATS instead.", "error")
        return redirect("/upload_resume_individual")

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
                j.application_deadline,
                COUNT(a.id) AS applicants,
                AVG(a.score) AS avg_score
            FROM jobs j
            LEFT JOIN applications a ON a.job_id = j.id
            WHERE j.recruiter_email = ?
            GROUP BY j.id, j.title, j.application_deadline
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

    @app.route("/student/jobs/<int:job_id>/apply", methods=["GET", "POST"])
    def apply_job(job_id):
        if not role_required("student"):
            flash("Student access required.", "error")
            return redirect("/")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
        job = cur.fetchone()
        if not job:
            conn.close()
            flash("Job not found.", "error")
            return redirect("/student/job-profile")

        if request.method == "POST":
            file = request.files.get("resume")
            if not file or not file.filename:
                conn.close()
                flash("Please select a document to apply.", "error")
                return redirect(f"/student/jobs/{job_id}/apply")

            filename = secure_filename(file.filename)
            path = os.path.join("uploads", filename)
            file.save(path)

            cur.execute(
                """
                INSERT INTO applications(student_email, job_id, resume_filename, score, missing_keywords)
                VALUES(?,?,?,?,?)
                """,
                (session["user"], job_id, filename, None, None),
            )
            conn.commit()
            conn.close()

            session["resume_filename"] = filename
            flash("Application submitted successfully.", "success")
            return redirect(f"/student/jobs/{job_id}")

        conn.close()
        return render_template("student_apply_job.html", job=job)

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

    @app.route("/post_job", methods=["GET", "POST"])
    def post_job():
        if not role_required("recruiter"):
            flash("Recruiter access required.", "error")
            return redirect("/")

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            skills = request.form.get("skills", "").strip()
            application_deadline = request.form.get("application_deadline", "").strip()

            if not title or not description:
                flash("Title and description are required.", "error")
                return redirect("/post_job")

            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                """
            INSERT INTO jobs(title, description, skills, recruiter_email, application_deadline)
            VALUES(?,?,?,?,?)
            """,
                (title, description, skills, session["user"], application_deadline or None),
            )

            conn.commit()
            conn.close()

            flash("Job posted successfully.", "success")
            return redirect("/recruiter")

        return render_template("post_job.html")

    @app.route("/recruiter/jobs/<int:job_id>")
    def recruiter_job_detail(job_id):
        if not role_required("recruiter"):
            flash("Recruiter access required.", "error")
            return redirect("/")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE id=? AND recruiter_email=?", (job_id, session["user"]))
        job = cur.fetchone()
        conn.close()

        if not job:
            flash("You can only access jobs posted from your recruiter account.", "error")
            return redirect("/recruiter")

        return render_template("recruiter_job_detail.html", job=job)

    @app.route("/recruiter/jobs/<int:job_id>/edit", methods=["GET", "POST"])
    def recruiter_edit_job(job_id):
        if not role_required("recruiter"):
            flash("Recruiter access required.", "error")
            return redirect("/")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE id=? AND recruiter_email=?", (job_id, session["user"]))
        job = cur.fetchone()
        if not job:
            conn.close()
            flash("You can only edit jobs posted from your recruiter account.", "error")
            return redirect("/recruiter")

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            skills = request.form.get("skills", "").strip()
            application_deadline = request.form.get("application_deadline", "").strip()

            if not title or not description:
                conn.close()
                flash("Title and description are required.", "error")
                return redirect(f"/recruiter/jobs/{job_id}/edit")

            cur.execute(
                """
                UPDATE jobs
                SET title=?, description=?, skills=?, application_deadline=?
                WHERE id=? AND recruiter_email=?
                """,
                (title, description, skills, application_deadline or None, job_id, session["user"]),
            )
            conn.commit()
            conn.close()
            flash("Job updated successfully.", "success")
            return redirect(f"/recruiter/jobs/{job_id}")

        conn.close()
        return render_template("edit_job.html", job=job)

    @app.route("/jobs")
    def jobs():
        if "user" not in session:
            flash("Please log in to view jobs.", "error")
            return redirect("/")

        conn = get_db_connection()
        cur = conn.cursor()
        if session.get("role") == "recruiter":
            cur.execute("SELECT * FROM jobs WHERE recruiter_email=? ORDER BY id DESC", (session["user"],))
        else:
            cur.execute("SELECT * FROM jobs ORDER BY id DESC")
        all_jobs = cur.fetchall()
        conn.close()

        return render_template("jobs.html", jobs=all_jobs, resume_uploaded="resume_text" in session)
