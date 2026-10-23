from collections.abc import Sequence

from src.database.connection import init_db
from src.database.repository import pr_exists, save_processed_pr, save_raw_pr
from src.ingestion.github_client import GitHubClient
from src.processing.gemini_client import GeminiProcessor


def validate_software_afectado(
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


def sync_repository(repo: str, limit: int = 15):
    print(f"=== Sincronizando repositorio: {repo} ===")
    init_db()

    gh_client = GitHubClient()
    ai_processor = GeminiProcessor()

    prs = gh_client.fetch_closed_prs(repo, limit=limit)
    print(f"PRs válidos obtenidos: {len(prs)}")

    nuevos = 0
    omitidos = 0

    for pr in prs:
        if pr_exists(repo, pr['id']):
            omitidos += 1
            continue

        try:
            save_raw_pr(repo, pr)
            print(f"\nProcesando #{pr['id']}: {pr['title']}...")
            analysis = ai_processor.analyze_pr(pr['title'], pr['body'])
            raw_payload = pr.get("_raw_payload", pr)
            source_text = (
                f"{raw_payload.get('title', pr['title'])}\n"
                f"{raw_payload.get('body') or pr['body']}"
            )
            analysis["software_afectado"] = validate_software_afectado(
                analysis["software_afectado"],
                source_text,
            )
            save_processed_pr(repo, pr, analysis)
            nuevos += 1
            print(f"  -> Guardado. Categoría: {analysis.get('categoria')} | Relevancia: {analysis.get('relevancia')}")
        except Exception as e:
            print(f"  -> Error procesando #{pr['id']}: {e}")

    print("\n" + "=" * 50)
    print(f"Resultado: {nuevos} añadidos | {omitidos} omitidos (preexistentes)")

if __name__ == "__main__":
    sync_repository("KytyPS5/KytyPS5", limit=10)