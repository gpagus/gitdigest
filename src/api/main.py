import json
from typing import Literal
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from src.database.connection import get_connection, init_db
from src.database.repository import (
    claim_sync,
    feedback_sent_recently,
    get_sync_status,
    mark_feedback_failed,
    mark_feedback_sent,
    save_feedback,
    sync_is_due,
)
from src.ingestion.github_client import GitHubAPIError, GitHubClient
from src.notifications.feedback_email import send_feedback_email
from src.services.sync_service import sync_repository

SYNC_COOLDOWN_SECONDS = 300


class FeedbackRequest(BaseModel):
    feedback_type: Literal["bug", "improvement", "other"]
    message: str = Field(min_length=10, max_length=3000)
    repo: str | None = Field(default=None, max_length=200)
    page_url: str | None = Field(default=None, max_length=500)
    website: str = Field(default="", max_length=100)


def notify_feedback(
    feedback_id: int,
    feedback_type: str,
    message: str,
    repo: str | None,
    page_url: str | None,
) -> None:
    try:
        sent = send_feedback_email(feedback_type, message, repo, page_url)
    except Exception as error:
        mark_feedback_failed(feedback_id, str(error))
    else:
        if sent:
            mark_feedback_sent(feedback_id)

app = FastAPI(
    title="GitDigest API",
    description="API para acceder a los datos procesados de los pull requests de GitHub.",
)


@app.post("/api/feedback", status_code=201)
def create_feedback(
    payload: FeedbackRequest,
    request: Request,
    background_tasks: BackgroundTasks,
):
    init_db()
    if payload.website:
        raise HTTPException(status_code=400, detail="Solicitud no válida.")

    ip_address = request.client.host if request.client else "unknown"
    if feedback_sent_recently(ip_address):
        raise HTTPException(
            status_code=429,
            detail="Has enviado feedback recientemente. Inténtalo más tarde.",
        )

    message = payload.message.strip()
    if len(message) < 10:
        raise HTTPException(
            status_code=422,
            detail="El mensaje debe tener al menos 10 caracteres.",
        )
    feedback_id = save_feedback(
        payload.feedback_type,
        message,
        payload.repo,
        payload.page_url,
        ip_address,
    )
    background_tasks.add_task(
        notify_feedback,
        feedback_id,
        payload.feedback_type,
        message,
        payload.repo,
        payload.page_url,
    )
    return {"message": "Feedback recibido. Gracias por ayudarnos a mejorar."}


@app.get("/api/feed/{owner}/{repo_name}")
def get_repo_feed(
    owner: str,
    repo_name: str,
    background_tasks: BackgroundTasks,
    limit: int = Query(20, ge=1, le=100),
):
    init_db()
    repo_full_name = f"{owner}/{repo_name}"
    conn = get_connection()
    try:
        rows = conn.execute('''
            SELECT pr_number, title, merged_at, url, categoria, subsistema,
                relevancia, es_ruido, impacto_usuario, resumen_tecnico,
                software_afectado, plataformas, accion_requerida, es_regresion
            FROM processed_prs
            WHERE repo = ? AND es_ruido = 0
            ORDER BY merged_at DESC
            LIMIT ?
        ''', (repo_full_name, limit)).fetchall()
        known = rows or conn.execute(
            "SELECT 1 FROM processed_prs WHERE repo = ? LIMIT 1", (repo_full_name,)
        ).fetchone()
    finally:
        conn.close()

    feed = []
    for row in rows:
        pr = dict(row)
        pr['software_afectado'] = json.loads(pr['software_afectado']) if pr['software_afectado'] else []
        pr['plataformas'] = json.loads(pr['plataformas']) if pr['plataformas'] else []
        pr['es_ruido'] = bool(pr['es_ruido'])
        pr['es_regresion'] = bool(pr['es_regresion'])
        feed.append(pr)

    sync_status = get_sync_status(repo_full_name)
    if sync_status and sync_status["status"] == "processing":
        if known:
            return {
                "repo": repo_full_name,
                "status": "processing",
                "message": "Hay una actualización en curso.",
                "resultados": len(feed),
                "data": feed,
            }
        return JSONResponse(
            status_code=202,
            content={
                "repo": repo_full_name,
                "status": "processing",
                "message": "El repositorio se está procesando.",
            },
        )

    if not sync_is_due(sync_status, SYNC_COOLDOWN_SECONDS):
        return {
            "repo": repo_full_name,
            "resultados": len(feed),
            "data": feed,
        }

    if not known:
        try:
            if not GitHubClient().repository_exists(repo_full_name):
                raise HTTPException(
                    status_code=404,
                    detail="Repositorio no encontrado en GitHub.",
                )
        except GitHubAPIError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    if claim_sync(repo_full_name):
        background_tasks.add_task(sync_repository, repo_full_name, limit)

    if known:
        return {
            "repo": repo_full_name,
            "status": "processing",
            "message": "Buscando actualizaciones nuevas.",
            "resultados": len(feed),
            "data": feed,
        }

    return JSONResponse(
        status_code=202,
        content={
            "repo": repo_full_name,
            "status": "processing",
            "message": "El repositorio se está procesando.",
        },
    )

@app.get("/health")
def health_check():
    return {"status": "ok"}