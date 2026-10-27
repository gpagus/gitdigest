import sqlite3
import os
import json
from src.config import DB_PATH

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_github_prs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                raw_payload TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(repo, pr_number)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_prs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                title TEXT NOT NULL,
                merged_at TEXT NOT NULL,
                url TEXT NOT NULL,
                categoria TEXT,
                subsistema TEXT,
                relevancia TEXT,
                es_ruido INTEGER,
                es_regresion INTEGER NOT NULL DEFAULT 0,
                impacto_usuario TEXT,
                resumen_tecnico TEXT,
                software_afectado TEXT,
                plataformas TEXT,
                accion_requerida TEXT,
                canonical_repo TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(repo, pr_number)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS repository_syncs (
                repo TEXT PRIMARY KEY,
                canonical_repo TEXT,
                status TEXT NOT NULL,
                error TEXT,
                started_at DATETIME,
                finished_at DATETIME
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feedback_type TEXT NOT NULL,
                message TEXT NOT NULL,
                repo TEXT,
                page_url TEXT,
                ip_address TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'stored',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                sent_at DATETIME,
                error TEXT
            )
        """)
        columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(processed_prs)")
        }
        if "es_regresion" not in columns:
            cursor.execute(
                "ALTER TABLE processed_prs ADD COLUMN es_regresion INTEGER NOT NULL DEFAULT 0"
            )
        if "canonical_repo" not in columns:
            cursor.execute(
                "ALTER TABLE processed_prs ADD COLUMN canonical_repo TEXT"
            )

        sync_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(repository_syncs)")
        }
        if "canonical_repo" not in sync_columns:
            cursor.execute(
                "ALTER TABLE repository_syncs ADD COLUMN canonical_repo TEXT"
            )

        missing_canonical = cursor.execute(
            """
            SELECT id, repo, pr_number
            FROM processed_prs
            WHERE canonical_repo IS NULL
            """
        ).fetchall()
        for row in missing_canonical:
            raw_row = cursor.execute(
                """
                SELECT raw_payload
                FROM raw_github_prs
                WHERE pr_number = ? AND lower(repo) = lower(?)
                LIMIT 1
                """,
                (row["pr_number"], row["repo"]),
            ).fetchone()
            if not raw_row:
                continue
            try:
                payload = json.loads(raw_row["raw_payload"])
            except (TypeError, json.JSONDecodeError):
                continue
            canonical_repo = (
                payload.get("base", {}).get("repo", {}).get("full_name")
                if isinstance(payload, dict)
                else None
            )
            if canonical_repo:
                cursor.execute(
                    "UPDATE processed_prs SET canonical_repo = ? WHERE id = ?",
                    (canonical_repo, row["id"]),
                )

        cursor.execute(
            """
            UPDATE repository_syncs
            SET canonical_repo = (
                SELECT COALESCE(processed.canonical_repo, processed.repo)
                FROM processed_prs AS processed
                WHERE lower(processed.repo) = lower(repository_syncs.repo)
                LIMIT 1
            )
            WHERE canonical_repo IS NULL
            """
        )
        conn.commit()
    finally:
        conn.close()