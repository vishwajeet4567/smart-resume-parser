from flask import session

from db import get_db_connection

"""
Authentication & Profile Helpers
Provides utility functions for role-based access control and fetching student profiles.
"""

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


def register_context_processors(app):
    @app.context_processor
    def inject_user_context():
        return {
            "is_logged_in": "user" in session,
            "user_email": session.get("user"),
            "role": session.get("role"),
        }
