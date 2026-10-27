import json
from datetime import datetime, timedelta, timezone

from src.database.connection import get_connection


def get_sync_status(repo: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT repo, status, error, started_at, finished_at "
            "FROM repository_syncs WHERE repo = ?",
            (repo,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def sync_is_due(status: dict | None, cooldown_seconds: int) -> bool:
    if not status or status["status"] == "processing":
        return False if status else True

    finished_at = status.get("finished_at")
    if not finished_at:
        return True

    try:
        completed_at = datetime.fromisoformat(finished_at)
    except ValueError:
        return True

    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - completed_at >= timedelta(seconds=cooldown_seconds)


def claim_sync(repo: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO repository_syncs (repo, status, started_at)
            VALUES (?, 'processing', ?)
            ON CONFLICT(repo) DO UPDATE SET
                status = 'processing',
                error = NULL,
                started_at = excluded.started_at,
                finished_at = NULL
            WHERE repository_syncs.status NOT IN ('processing', 'pending')
            """,
            (repo, now),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def finish_sync(repo: str, status: str, error: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE repository_syncs
            SET status = ?, error = ?, finished_at = ?
            WHERE repo = ?
            """,
            (status, error, now, repo),
        )
        conn.commit()
    finally:
        conn.close()


def feedback_sent_recently(ip_address: str, window_minutes: int = 15) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT 1 FROM feedback
            WHERE ip_address = ?
              AND created_at >= datetime('now', ?)
            LIMIT 1
            """,
            (ip_address, f"-{window_minutes} minutes"),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def save_feedback(
    feedback_type: str,
    message: str,
    repo: str | None,
    page_url: str | None,
    ip_address: str,
) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO feedback
                (feedback_type, message, repo, page_url, ip_address)
            VALUES (?, ?, ?, ?, ?)
            """,
            (feedback_type, message, repo, page_url, ip_address),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def mark_feedback_sent(feedback_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE feedback
            SET status = 'sent', sent_at = CURRENT_TIMESTAMP, error = NULL
            WHERE id = ?
            """,
            (feedback_id,),
        )
        conn.commit()
    finally:
        conn.close()


def mark_feedback_failed(feedback_id: int, error: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE feedback SET status = 'failed', error = ? WHERE id = ?",
            (error[:500], feedback_id),
        )
        conn.commit()
    finally:
        conn.close()


def pr_exists(repo: str, pr_number: int) -> bool:
    """Comprueba si un PR ya tiene una salida procesada."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM processed_prs WHERE repo = ? AND pr_number = ?",
            (repo, pr_number),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def save_raw_pr(repo: str, pr_data: dict) -> None:
    """Guarda el payload original del PR sin sobrescribirlo."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO raw_github_prs
                (repo, pr_number, raw_payload)
            VALUES (?, ?, ?)
            """,
            (
                repo,
                pr_data["id"],
                json.dumps(
                    pr_data.get("_raw_payload", pr_data),
                    ensure_ascii=False,
                ),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def save_processed_pr(repo: str, pr_data: dict, ia_data: dict) -> None:
    """Guarda o actualiza la salida estructurada del modelo."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO processed_prs
                (repo, pr_number, title, merged_at, url, categoria, subsistema,
                 relevancia, es_ruido, es_regresion, impacto_usuario,
                 resumen_tecnico, software_afectado, plataformas, accion_requerida)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(repo, pr_number) DO UPDATE SET
                title = excluded.title,
                merged_at = excluded.merged_at,
                url = excluded.url,
                categoria = excluded.categoria,
                subsistema = excluded.subsistema,
                relevancia = excluded.relevancia,
                es_ruido = excluded.es_ruido,
                es_regresion = excluded.es_regresion,
                impacto_usuario = excluded.impacto_usuario,
                resumen_tecnico = excluded.resumen_tecnico,
                software_afectado = excluded.software_afectado,
                plataformas = excluded.plataformas,
                accion_requerida = excluded.accion_requerida
            """,
            (
                repo,
                pr_data["id"],
                pr_data["title"],
                pr_data["merged_at"],
                pr_data["url"],
                ia_data["categoria"],
                ia_data["subsistema"],
                ia_data["relevancia"],
                int(ia_data["es_ruido"]),
                int(ia_data["es_regresion"]),
                ia_data["impacto_usuario"],
                ia_data["resumen_tecnico"],
                json.dumps(ia_data["software_afectado"], ensure_ascii=False),
                json.dumps(ia_data["plataformas"], ensure_ascii=False),
                ia_data["accion_requerida"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def save_pr(repo: str, pr_data: dict, ia_data: dict) -> None:
    """Guarda primero el raw y después la salida procesada."""
    save_raw_pr(repo, pr_data)
    save_processed_pr(repo, pr_data, ia_data)