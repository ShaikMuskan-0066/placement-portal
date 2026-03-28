"""SQLite access: connection helpers and data operations."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

DB_NAME = "database.db"


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_connection():
    """Yield a connection; always close. Commit inside the block for writes."""
    conn = connect_db()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS experience (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                senior_name TEXT NOT NULL DEFAULT '',
                company TEXT NOT NULL,
                passout_year INTEGER,
                role TEXT NOT NULL,
                questions TEXT,
                prep TEXT,
                courses TEXT,
                "user" TEXT
            )
            """
        )
        _ensure_experience_columns(conn)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                asked_by INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                answer TEXT,
                answered_by INTEGER,
                answered_at TEXT,
                FOREIGN KEY (asked_by) REFERENCES users(id),
                FOREIGN KEY (answered_by) REFERENCES users(id)
            )
            """
        )
        conn.commit()


def _ensure_experience_columns(conn: sqlite3.Connection) -> None:
    """Add senior_name / passout_year when upgrading an older database."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(experience)")
    existing = {row[1] for row in cur.fetchall()}
    if "senior_name" not in existing:
        cur.execute(
            "ALTER TABLE experience ADD COLUMN senior_name TEXT NOT NULL DEFAULT ''"
        )
    if "passout_year" not in existing:
        cur.execute("ALTER TABLE experience ADD COLUMN passout_year INTEGER")
    if "user" not in existing:
        cur.execute('ALTER TABLE experience ADD COLUMN "user" TEXT')
    conn.commit()


def get_user_by_credentials(username: str, password: str) -> sqlite3.Row | None:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username FROM users WHERE username = ? AND password = ?",
            (username, password),
        )
        return cur.fetchone()


def create_user(username: str, password: str) -> None:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password),
        )
        conn.commit()


def fetch_queries(limit: int | None = None, unanswered_first: bool = False):
    order = "ORDER BY q.created_at DESC"
    if unanswered_first:
        order = """
        ORDER BY CASE WHEN q.answer IS NULL OR TRIM(q.answer) = '' THEN 0 ELSE 1 END,
                 q.created_at DESC
        """
    sql = f"""
        SELECT q.id, q.question, q.answer, q.created_at, q.answered_at,
               u.username AS asker_name,
               ans.username AS answerer_name
        FROM queries q
        JOIN users u ON u.id = q.asked_by
        LEFT JOIN users ans ON ans.id = q.answered_by
        {order}
    """
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
    if limit is not None:
        rows = rows[:limit]
    return rows


def fetch_experience_count_by_company() -> tuple[list[str], list[int]]:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT MIN(TRIM(company)) AS company, COUNT(*) AS cnt
            FROM experience
            GROUP BY LOWER(TRIM(company))
            ORDER BY cnt DESC, company ASC
            """
        )
        rows = cur.fetchall()
    labels = [r["company"] for r in rows]
    counts = [r["cnt"] for r in rows]
    return labels, counts


def fetch_all_experiences():
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM experience ORDER BY id DESC")
        return cur.fetchall()


def fetch_experiences_for_user(username: str):
    """Rows where experience owner matches session username (sqlite3.Row)."""
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            'SELECT * FROM experience WHERE "user" = ? ORDER BY id DESC',
            (username,),
        )
        return cur.fetchall()


def get_experience_by_id(experience_id: int) -> sqlite3.Row | None:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM experience WHERE id = ?", (experience_id,))
        return cur.fetchone()


def insert_experience(
    senior_name: str,
    company: str,
    passout_year: int | None,
    role: str,
    questions: str,
    prep: str,
    courses: str,
    user: str,
) -> None:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO experience (senior_name, company, passout_year, role, questions, prep, courses, "user")
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (senior_name, company, passout_year, role, questions, prep, courses, user),
        )
        conn.commit()


def update_experience(
    experience_id: int,
    owner_username: str,
    senior_name: str,
    company: str,
    passout_year: int | None,
    role: str,
    questions: str,
    prep: str,
    courses: str,
) -> bool:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE experience SET
                senior_name = ?, company = ?, passout_year = ?, role = ?,
                questions = ?, prep = ?, courses = ?
            WHERE id = ? AND "user" = ?
            """,
            (
                senior_name,
                company,
                passout_year,
                role,
                questions,
                prep,
                courses,
                experience_id,
                owner_username,
            ),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_experience_for_user(experience_id: int, owner_username: str) -> bool:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            'DELETE FROM experience WHERE id = ? AND "user" = ?',
            (experience_id, owner_username),
        )
        conn.commit()
        return cur.rowcount > 0


def insert_query(question: str, asked_by: int) -> None:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO queries (question, asked_by) VALUES (?, ?)",
            (question, asked_by),
        )
        conn.commit()


def get_query_for_answer(query_id: int) -> sqlite3.Row | None:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT q.id, q.question, q.answer, q.created_at, q.answered_at, q.asked_by,
                   u.username AS asker_name
            FROM queries q
            JOIN users u ON u.id = q.asked_by
            WHERE q.id = ?
            """,
            (query_id,),
        )
        return cur.fetchone()


def save_query_answer(query_id: int, answer: str, answered_by: int) -> None:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE queries
            SET answer = ?, answered_by = ?, answered_at = datetime('now')
            WHERE id = ?
            """,
            (answer, answered_by, query_id),
        )
        conn.commit()
