import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from src.database.connection import get_connection

app = FastAPI(
    title="GitDigest API",
    description="API para acceder a los datos procesados de los pull requests de GitHub.",
)

@app.get("/api/feed/{owner}/{repo_name}")
def get_repo_feed(owner: str, repo_name: str, limit: int = 20):
    repo_full_name = f"{owner}/{repo_name}"
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT pr_number, title, merged_at, url, categoria, subsistema, 
                relevancia, es_ruido, impacto_usuario, resumen_tecnico, 
                software_afectado, plataformas, accion_requerida, es_regresion
            FROM processed_prs
            WHERE repo = ?
            ORDER BY merged_at DESC
            LIMIT ?
        ''', (repo_full_name, limit))
        
        rows = cursor.fetchall()
        
        if not rows:
            raise HTTPException(status_code=404, detail="Repositorio no encontrado o sin datos procesados.")
            
        feed = []
        for row in rows:
            pr = dict(row)
            
            # Reconvertir los campos JSON de SQLite a listas de Python
            pr['software_afectado'] = json.loads(pr['software_afectado']) if pr['software_afectado'] else []
            pr['plataformas'] = json.loads(pr['plataformas']) if pr['plataformas'] else []
            
            pr['es_ruido'] = bool(pr['es_ruido'])
            pr['es_regresion'] = bool(pr.get('es_regresion', False))
            
            feed.append(pr)
            
        return {
            "repo": repo_full_name,
            "resultados": len(feed),
            "data": feed
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/health")
def health_check():
    return {"status": "ok"}