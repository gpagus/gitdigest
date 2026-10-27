import os
from pathlib import Path
from dotenv import load_dotenv

# Carga variables desde el archivo .env en la raíz
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DB_PATH = str(ROOT_DIR / "data" / "tracker.db")
FEEDBACK_SMTP_HOST = os.getenv("FEEDBACK_SMTP_HOST")
FEEDBACK_SMTP_PORT = int(os.getenv("FEEDBACK_SMTP_PORT", "587"))
FEEDBACK_SMTP_USER = os.getenv("FEEDBACK_SMTP_USER")
FEEDBACK_SMTP_PASSWORD = os.getenv("FEEDBACK_SMTP_PASSWORD")
FEEDBACK_FROM_EMAIL = os.getenv("FEEDBACK_FROM_EMAIL")
FEEDBACK_TO_EMAIL = os.getenv("FEEDBACK_TO_EMAIL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "https://gitdigest-ia.vercel.app,http://127.0.0.1:4321",
    ).split(",")
    if origin.strip()
]

if not GITHUB_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Faltan variables de entorno requeridas en el archivo .env")