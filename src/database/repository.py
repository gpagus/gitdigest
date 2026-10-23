import json

from src.database.connection import get_connection


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