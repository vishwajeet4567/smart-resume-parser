import sqlite3


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
        recruiter_email TEXT,
        application_deadline TEXT
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

    # Backward-compatible schema update for existing databases.
    cur.execute("PRAGMA table_info(jobs)")
    job_columns = {row[1] for row in cur.fetchall()}
    if "application_deadline" not in job_columns:
        cur.execute("ALTER TABLE jobs ADD COLUMN application_deadline TEXT")

    conn.commit()
    conn.close()


def get_db_connection():
    conn = sqlite3.connect("database.db", timeout=10)
    conn.row_factory = sqlite3.Row
    return conn
