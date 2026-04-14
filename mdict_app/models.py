import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "database.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dictionaries (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            filename TEXT NOT NULL,
            title TEXT,
            version TEXT,
            entry_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            id TEXT PRIMARY KEY,
            dict_id TEXT NOT NULL,
            keyword TEXT NOT NULL,
            content_html TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (dict_id) REFERENCES dictionaries(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_dict_id ON entries(dict_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_keyword ON entries(keyword)")

    conn.commit()
    conn.close()


class Dictionary:
    @staticmethod
    def create(name, filename, title=None, version=None, entry_count=0):
        dict_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO dictionaries (id, name, filename, title, version, entry_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (dict_id, name, filename, title, version, entry_count, now),
        )
        conn.commit()
        conn.close()
        return {
            "id": dict_id,
            "name": name,
            "filename": filename,
            "title": title,
            "version": version,
            "entry_count": entry_count,
            "created_at": now,
        }

    @staticmethod
    def list_all():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dictionaries ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_by_id(dict_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dictionaries WHERE id = ?", (dict_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def delete(dict_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dictionaries WHERE id = ?", (dict_id,))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def update_entry_count(dict_id, entry_count):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE dictionaries SET entry_count = ? WHERE id = ?",
            (entry_count, dict_id),
        )
        conn.commit()
        conn.close()


class Entry:
    @staticmethod
    def insert_many(entries):
        if not entries:
            return
        conn = get_db()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.executemany(
            """
            INSERT INTO entries (id, dict_id, keyword, content_html, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (str(uuid.uuid4()), e["dict_id"], e["keyword"], e["content_html"], now)
                for e in entries
            ],
        )
        conn.commit()
        conn.close()

    @staticmethod
    def search(dict_id, keyword, limit=50, offset=0):
        conn = get_db()
        cursor = conn.cursor()
        pattern = f"%{keyword}%"
        cursor.execute(
            """
            SELECT id, keyword FROM entries
            WHERE dict_id = ? AND keyword LIKE ?
            ORDER BY keyword ASC
            LIMIT ? OFFSET ?
            """,
            (dict_id, pattern, limit, offset),
        )
        rows = cursor.fetchall()
        cursor.execute(
            """
            SELECT COUNT(*) as total FROM entries
            WHERE dict_id = ? AND keyword LIKE ?
            """,
            (dict_id, pattern),
        )
        total = cursor.fetchone()["total"]
        conn.close()
        return {"items": [dict(row) for row in rows], "total": total}

    @staticmethod
    def list_by_dict(dict_id, limit=50, offset=0):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, keyword FROM entries
            WHERE dict_id = ?
            ORDER BY keyword ASC
            LIMIT ? OFFSET ?
            """,
            (dict_id, limit, offset),
        )
        rows = cursor.fetchall()
        cursor.execute(
            """
            SELECT COUNT(*) as total FROM entries WHERE dict_id = ?
            """,
            (dict_id,),
        )
        total = cursor.fetchone()["total"]
        conn.close()
        return {"items": [dict(row) for row in rows], "total": total}

    @staticmethod
    def get_by_id(entry_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM entries WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def delete_by_dict(dict_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM entries WHERE dict_id = ?", (dict_id,))
        conn.commit()
        conn.close()
        return True
