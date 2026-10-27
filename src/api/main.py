from typing import Literal
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from src.database.connection import init_db
from src.config import CORS_ORIGINS
from src.database.repository import (
    claim_sync,
    feedback_sent_recently,
    get_sync_status,
    mark_feedback_failed,
    mark_feedback_sent,
    save_feedback,
    sync_is_due,
    get_cached_digest,
    get_cached_feed,
    get_latest_digests,
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
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
    digest = get_cached_digest(repo_full_name)
    feed = get_cached_feed(repo_full_name, limit)
    known = digest is not None
    response_repo = digest["repo"] if digest else repo_full_name

    sync_status = get_sync_status(response_repo)
    if sync_status and sync_status["status"] == "processing":
        if known:
            return {
                "repo": response_repo,
                "status": "processing",
                "message": "Hay una actualización en curso.",
                "resultados": len(feed),
                "data": feed,
            }
        return JSONResponse(
            status_code=202,
            content={
                "repo": response_repo,
                "status": "processing",
                "message": "El repositorio se está procesando.",
            },
        )

    if not sync_is_due(sync_status, SYNC_COOLDOWN_SECONDS):
        return {
            "repo": response_repo,
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
            "repo": response_repo,
            "status": "processing",
            "message": "Buscando actualizaciones nuevas.",
            "resultados": len(feed),
            "data": feed,
        }

    return JSONResponse(
        status_code=202,
        content={
            "repo": response_repo,
            "status": "processing",
            "message": "El repositorio se está procesando.",
        },
    )


@app.get("/api/digests")
def get_latest_repo_digests(limit: int = Query(6, ge=1, le=6)):
    init_db()
    return {"data": get_latest_digests(limit)}


@app.get("/api/digests/{owner}/{repo_name}")
def get_cached_repo_digest(
    owner: str,
    repo_name: str,
    limit: int = Query(20, ge=1, le=100),
):
    init_db()
    requested_repo = f"{owner}/{repo_name}"
    digest = get_cached_digest(requested_repo)
    if not digest:
        raise HTTPException(status_code=404, detail="Digest no encontrado en caché.")

    feed = get_cached_feed(requested_repo, limit)
    return {
        "repo": digest["repo"],
        "resultados": len(feed),
        "data": feed,
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}