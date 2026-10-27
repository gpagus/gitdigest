import sqlite3
import os
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
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(repo, pr_number)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS repository_syncs (
                repo TEXT PRIMARY KEY,
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
        conn.commit()
    finally:
        conn.close()