from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel
from src.config import GEMINI_API_KEY
from src.processing.prompts import SYSTEM_PROMPT


class PRAnalysis(BaseModel):
    categoria: Literal[
        "Compatibilidad",
        "Rendimiento",
        "Corrección de Bugs",
        "Interfaz/QoL",
        "Interno",
    ]
    subsistema: Literal[
        "Gráficos",
        "Audio",
        "CPU/Memoria",
        "Input",
        "Interfaz",
        "Red",
        "General/Build",
    ]
    relevancia: Literal["Alta", "Media", "Baja"]
    es_ruido: bool
    es_regresion: bool
    impacto_usuario: str
    resumen_tecnico: str
    software_afectado: list[str]
    plataformas: list[str]
    accion_requerida: str | None


class GeminiProcessor:
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    def analyze_pr(self, title: str, body: str) -> dict:
        content = f"Título del PR: {title}\nDescripción:\n{body}"
        
        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=content,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=PRAnalysis,
                temperature=0.2
            )
        )
        if response.parsed is None:
            raise ValueError("Gemini no devolvió una respuesta estructurada válida")
        parsed = response.parsed
        if not isinstance(parsed, PRAnalysis):
            parsed = PRAnalysis.model_validate(parsed)
        return parsed.model_dump()