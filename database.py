import json
import random
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_NAME = "study.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def _table_columns(cursor: sqlite3.Cursor, table_name: str) -> list[str]:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def initialize_db() -> None:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                review_count INTEGER DEFAULT 0,
                confidence INTEGER DEFAULT 0,
                last_reviewed DATETIME NULL,
                created_at DATETIME
            )
            """
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_subject_topic ON topics(LOWER(subject), LOWER(topic))"
        )

        columns = _table_columns(cursor, "topics")
        if "review_count" not in columns:
            cursor.execute("ALTER TABLE topics ADD COLUMN review_count INTEGER DEFAULT 0")
        if "confidence" not in columns:
            cursor.execute("ALTER TABLE topics ADD COLUMN confidence INTEGER DEFAULT 0")
        if "last_reviewed" not in columns:
            cursor.execute("ALTER TABLE topics ADD COLUMN last_reviewed DATETIME NULL")
        if "created_at" not in columns:
            cursor.execute("ALTER TABLE topics ADD COLUMN created_at DATETIME")
        if "counter" in columns and "review_count" in columns:
            cursor.execute(
                "UPDATE topics SET review_count = counter WHERE (review_count IS NULL OR review_count = 0) AND counter IS NOT NULL"
            )
        connection.commit()


def get_all_topics() -> list[dict[str, Any]]:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, subject, topic, review_count, confidence, last_reviewed, created_at FROM topics ORDER BY LOWER(subject), LOWER(topic)"
        )
        return [dict(row) for row in cursor.fetchall()]


def fetch_topic(topic_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, subject, topic, review_count, confidence, last_reviewed, created_at FROM topics WHERE id = ?",
            (topic_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def create_topic(
    subject: str,
    topic: str,
    review_count: int = 0,
    confidence: int = 0,
    last_reviewed: str | None = None,
    created_at: str | None = None,
) -> int:
    created_at = created_at or datetime.utcnow().isoformat()
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO topics (subject, topic, review_count, confidence, last_reviewed, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (subject.strip(), topic.strip(), review_count, confidence, last_reviewed, created_at),
        )
        connection.commit()
        return cursor.lastrowid


def update_topic(topic_id: int, subject: str, topic: str) -> None:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE topics SET subject = ?, topic = ? WHERE id = ?",
            (subject.strip(), topic.strip(), topic_id),
        )
        connection.commit()


def delete_topic(topic_id: int) -> None:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
        connection.commit()


def record_review(topic_id: int, difficulty: str) -> None:
    topic = fetch_topic(topic_id)
    if topic is None:
        return

    review_count = int(topic["review_count"] or 0) + 1
    confidence = int(topic["confidence"] or 0)
    if difficulty == "easy":
        confidence += 1
    elif difficulty == "hard":
        confidence = max(confidence - 1, 0)

    last_reviewed = datetime.utcnow().isoformat()
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE topics SET review_count = ?, confidence = ?, last_reviewed = ? WHERE id = ?",
            (review_count, confidence, last_reviewed, topic_id),
        )
        connection.commit()


def get_random_topic() -> dict[str, Any] | None:
    topics = get_all_topics()
    if not topics:
        return None

    weights = [max(1, 5 - int(topic["confidence"] or 0)) for topic in topics]
    selected = random.choices(topics, weights=weights, k=1)[0]
    return selected


def import_json(filepath: str) -> tuple[int, int]:
    path = Path(filepath)
    if not path.exists():
        raise ValueError("File does not exist.")

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict) or "subjects" not in payload:
        raise ValueError("JSON must contain a top-level 'subjects' field.")

    inserted = 0
    skipped = 0
    with get_connection() as connection:
        cursor = connection.cursor()
        for subject_item in payload.get("subjects", []):
            subject_name = subject_item.get("name")
            if not subject_name or not isinstance(subject_name, str):
                continue

            for subtopic in subject_item.get("subtopics", []):
                topic_name = subtopic.get("name")
                review_count = int(subtopic.get("counter", 0) or 0)
                if not topic_name or not isinstance(topic_name, str):
                    continue

                cursor.execute(
                    "INSERT OR IGNORE INTO topics (subject, topic, review_count, confidence, last_reviewed, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        subject_name.strip(),
                        topic_name.strip(),
                        review_count,
                        0,
                        None,
                        datetime.utcnow().isoformat(),
                    ),
                )
                if cursor.rowcount:
                    inserted += 1
                else:
                    skipped += 1
        connection.commit()

    return inserted, skipped


def export_backup() -> str:
    subjects: dict[str, list[dict[str, Any]]] = {}
    for topic in get_all_topics():
        subject_name = topic["subject"]
        subjects.setdefault(subject_name, []).append(
            {"name": topic["topic"], "counter": int(topic["review_count"] or 0)}
        )

    payload = {
        "subjects": [
            {"name": subject_name, "subtopics": subtopics}
            for subject_name, subtopics in subjects.items()
        ]
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
