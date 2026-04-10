"""
单词 OCR 识别应用的数据模型
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "database.db"


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db()
    cursor = conn.cursor()

    # 任务表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 图片表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            ocr_result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    """)

    # 单词条目表（一个单词多行）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS word_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            image_id TEXT NOT NULL,
            word TEXT NOT NULL,
            cet4_count INTEGER DEFAULT 0,
            seq_num INTEGER NOT NULL,  -- 顺序号（1,2,3...），不是真题题号
            original_text TEXT NOT NULL,
            source TEXT,
            translation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


class Task:
    """任务模型"""

    @staticmethod
    def create(name: str) -> dict:
        """创建新任务"""
        task_id = str(uuid.uuid4())[:8]
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (id, name, status) VALUES (?, ?, ?)",
            (task_id, name, "pending"),
        )
        conn.commit()
        task = Task.get_by_id(task_id)
        conn.close()
        return task

    @staticmethod
    def get_by_id(task_id: str) -> dict:
        """根据 ID 获取任务"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    @staticmethod
    def list_all() -> list:
        """获取所有任务列表"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def update_status(task_id: str, status: str):
        """更新任务状态"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, task_id),
        )
        conn.commit()
        conn.close()


class Image:
    """图片模型"""

    @staticmethod
    def create(task_id: str, filename: str, stored_path: str) -> dict:
        """添加图片到任务"""
        image_id = str(uuid.uuid4())[:8]
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO images (id, task_id, filename, stored_path, status) VALUES (?, ?, ?, ?, ?)",
            (image_id, task_id, filename, stored_path, "pending"),
        )
        conn.commit()
        image = Image.get_by_id(image_id)
        conn.close()
        return image

    @staticmethod
    def get_by_id(image_id: str) -> dict:
        """根据 ID 获取图片"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    @staticmethod
    def list_by_task(task_id: str) -> list:
        """获取任务的所有图片"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM images WHERE task_id = ? ORDER BY created_at", (task_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def update_status(image_id: str, status: str, ocr_result: dict = None):
        """更新图片状态和 OCR 结果"""
        conn = get_db()
        cursor = conn.cursor()
        if ocr_result is not None:
            cursor.execute(
                "UPDATE images SET status = ?, ocr_result = ? WHERE id = ?",
                (status, json.dumps(ocr_result, ensure_ascii=False), image_id),
            )
        else:
            cursor.execute(
                "UPDATE images SET status = ? WHERE id = ?", (status, image_id)
            )
        conn.commit()
        conn.close()

    @staticmethod
    def list_pending_by_task(task_id: str) -> list:
        """获取任务中待处理的图片"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM images WHERE task_id = ? AND status = 'pending' ORDER BY created_at",
            (task_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


class WordEntry:
    """单词条目模型"""

    @staticmethod
    def create(
        task_id: str,
        image_id: str,
        word: str,
        cet4_count: int,
        seq_num: int,
        original_text: str,
        source: str = None,
        translation: str = None,
    ) -> dict:
        """创建单词条目"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO word_entries
                (task_id, image_id, word, cet4_count, seq_num, original_text, source, translation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task_id,
                image_id,
                word,
                cet4_count,
                seq_num,
                original_text,
                source,
                translation,
            ),
        )
        entry_id = cursor.lastrowid
        conn.commit()
        entry = WordEntry.get_by_id(entry_id)
        conn.close()
        return entry

    @staticmethod
    def get_by_id(entry_id: int) -> dict:
        """根据 ID 获取条目"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM word_entries WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    @staticmethod
    def list_by_task(task_id: str) -> list:
        """获取任务的所有单词条目（按插入顺序，即图片中的从上到下顺序）"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM word_entries
                WHERE task_id = ?
                ORDER BY id ASC""",
            (task_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def update_translation(entry_id: int, translation: str):
        """更新翻译"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE word_entries SET translation = ? WHERE id = ?",
            (translation, entry_id),
        )
        conn.commit()
        conn.close()
