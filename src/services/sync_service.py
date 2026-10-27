from src.config import GITHUB_TOKEN
from src.database.connection import init_db
from src.database.repository import finish_sync, pr_exists, save_processed_pr, save_raw_pr
from src.ingestion.github_client import GitHubClient
from src.processing.gemini_client import GeminiProcessor

BATCH_SIZE = 5


def sync_repository(repo: str, limit: int = 15) -> None:
    print(f"=== Sincronizando repositorio: {repo} ===")
    init_db()

    try:
        gh_client = GitHubClient()
        ai_processor = GeminiProcessor()

        prs = gh_client.fetch_closed_prs(repo, limit=limit)
        print(f"PRs válidos obtenidos: {len(prs)}")

        nuevos = 0
        omitidos = 0
        pendientes = []
        for pr in prs:
            if pr_exists(repo, pr["id"]):
                omitidos += 1
                continue
            save_raw_pr(repo, pr)
            pendientes.append(pr)

        for start in range(0, len(pendientes), BATCH_SIZE):
            batch = pendientes[start:start + BATCH_SIZE]
            try:
                print(f"\nAnalizando lote de {len(batch)} PR...")
                analyses = ai_processor.analyze_batch(batch)
            except Exception as error:
                print(f"  -> Lote no procesado: {error}")
                continue

            for pr in batch:
                try:
                    print(f"Procesando #{pr['id']}: {pr['title']}...")
                    analysis = analyses[pr["id"]]
                    raw_payload = pr.get("_raw_payload", pr)
                    source_text = (
                        f"{raw_payload.get('title', pr['title'])}\n"
                        f"{raw_payload.get('body') or pr['body']}"
                    )
                    analysis["software_afectado"] = ai_processor.validate_software_afectado(
                        analysis["software_afectado"],
                        source_text,
                    )
                    save_processed_pr(repo, pr, analysis)
                    nuevos += 1
                    print(
                        f"  -> Guardado. Categoría: {analysis.get('categoria')} | "
                        f"Relevancia: {analysis.get('relevancia')}"
                    )
                except Exception as error:
                    print(f"  -> Error procesando #{pr['id']}: {error}")

        pendientes_count = len(pendientes) - nuevos
        finish_sync(repo, "partial" if pendientes_count else "completed")
        print("\n" + "=" * 50)
        print(
            f"Resultado: {nuevos} añadidos | {omitidos} omitidos "
            f"(preexistentes) | {len(pendientes) - nuevos} pendientes"
        )
    except Exception as error:
        finish_sync(repo, "failed", str(error))
        print(f"Error sincronizando {repo}: {error}")

