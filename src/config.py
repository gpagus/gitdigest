import os
from pathlib import Path
from dotenv import load_dotenv

# Carga variables desde el archivo .env en la raíz
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DB_PATH = str(ROOT_DIR / "data" / "tracker.db")

if not GITHUB_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Faltan variables de entorno requeridas en el archivo .env")