"""Delete all rows from the experience table in database.db."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "database.db"


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM experience")
        conn.commit()
        deleted = cur.rowcount
    finally:
        conn.close()

    print(f"Done: removed {deleted} row(s) from experience (database: {DB_PATH}).")


if __name__ == "__main__":
    main()
