from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel
from src.config import GEMINI_API_KEY
from src.processing.prompts import SYSTEM_PROMPT

from collections.abc import Sequence



class PRAnalysisFields(BaseModel):
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


class PRAnalysis(PRAnalysisFields):
    pr_number: int


class PRBatchAnalysis(BaseModel):
    analyses: list[PRAnalysis]


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
                response_schema=PRAnalysisFields,
                temperature=0.2
            )
        )
        if response.parsed is None:
            raise ValueError("Gemini no devolvió una respuesta estructurada válida")
        parsed = response.parsed
        if not isinstance(parsed, PRAnalysisFields):
            parsed = PRAnalysisFields.model_validate(parsed)
        return parsed.model_dump()

    def analyze_batch(self, prs: list[dict]) -> dict[int, dict]:
        content = "\n\n".join(
            f"PR #{pr['id']}\nTítulo: {pr['title']}\nDescripción:\n{pr['body']}"
            for pr in prs
        )
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=content,
            config=types.GenerateContentConfig(
                system_instruction=(
                    f"{SYSTEM_PROMPT}\n"
                    "Analiza todos los PR proporcionados. Devuelve exactamente un "
                    "análisis por PR y conserva su número en pr_number."
                ),
                response_mime_type="application/json",
                response_schema=PRBatchAnalysis,
                temperature=0.2,
            ),
        )
        if response.parsed is None:
            raise ValueError("Gemini no devolvió un lote estructurado válido")

        parsed = response.parsed
        if not isinstance(parsed, PRBatchAnalysis):
            parsed = PRBatchAnalysis.model_validate(parsed)

        expected_ids = {pr["id"] for pr in prs}
        analyses = {
            analysis.pr_number: analysis.model_dump(exclude={"pr_number"})
            for analysis in parsed.analyses
        }
        if set(analyses) != expected_ids:
            missing = expected_ids - set(analyses)
            extra = set(analyses) - expected_ids
            raise ValueError(
                f"El lote de Gemini no coincide con los PR enviados "
                f"(faltan: {sorted(missing)}, sobran: {sorted(extra)})"
            )
        return analyses
    
    def validate_software_afectado(
        self,
        software_afectado: Sequence[str],
        source_text: str,
    ) -> list[str]:
        """Conserva únicamente entidades mencionadas en el texto fuente."""
        source_lower = source_text.lower()
        return [
            software
            for software in software_afectado
            if isinstance(software, str) and software.lower() in source_lower
        ]
