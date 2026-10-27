import smtplib
from email.message import EmailMessage

import requests

from src.config import (
    FEEDBACK_FROM_EMAIL,
    FEEDBACK_SMTP_HOST,
    FEEDBACK_SMTP_PASSWORD,
    FEEDBACK_SMTP_PORT,
    FEEDBACK_SMTP_USER,
    FEEDBACK_TO_EMAIL,
    RESEND_API_KEY,
)


def send_feedback_email(
    feedback_type: str,
    message: str,
    repo: str | None,
    page_url: str | None,
) -> bool:
    if RESEND_API_KEY and FEEDBACK_FROM_EMAIL and FEEDBACK_TO_EMAIL:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": FEEDBACK_FROM_EMAIL,
                "to": [FEEDBACK_TO_EMAIL],
                "subject": f"Nuevo feedback de GitDigest: {feedback_type}",
                "text": "\n".join(
                    [
                        "Nuevo feedback de GitDigest",
                        "",
                        f"Tipo: {feedback_type}",
                        f"Repositorio: {repo or 'No indicado'}",
                        f"URL: {page_url or 'No indicada'}",
                        "",
                        message,
                    ]
                ),
            },
            timeout=15,
        )
        response.raise_for_status()
        return True

    settings = (
        FEEDBACK_SMTP_HOST,
        FEEDBACK_SMTP_USER,
        FEEDBACK_SMTP_PASSWORD,
        FEEDBACK_FROM_EMAIL,
        FEEDBACK_TO_EMAIL,
    )
    if not all(settings):
        return False

    email = EmailMessage()
    email["Subject"] = f"Nuevo feedback de GitDigest: {feedback_type}"
    email["From"] = FEEDBACK_FROM_EMAIL
    email["To"] = FEEDBACK_TO_EMAIL
    email.set_content(
        "\n".join(
            [
                "Nuevo feedback de GitDigest",
                "",
                f"Tipo: {feedback_type}",
                f"Repositorio: {repo or 'No indicado'}",
                f"URL: {page_url or 'No indicada'}",
                "",
                message,
            ]
        )
    )

    with smtplib.SMTP(FEEDBACK_SMTP_HOST, FEEDBACK_SMTP_PORT, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(FEEDBACK_SMTP_USER, FEEDBACK_SMTP_PASSWORD)
        smtp.send_message(email)
    return True
