import requests
from src.config import GITHUB_TOKEN

class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

    def fetch_closed_prs(self, repo: str, limit: int = 20) -> list[dict]:
        url = f"{self.BASE_URL}/repos/{repo}/pulls"
        params = {"state": "closed", "per_page": limit}
        
        response = requests.get(url, headers=self.headers, params=params)
        if response.status_code != 200:
            print(f"Error consultando GitHub API ({response.status_code}): {response.text}")
            return []

        valid_prs = []
        for pr in response.json():
            # Filtros de descarte
            if not pr.get("merged_at"):
                continue
            if pr.get("draft") or "[draft]" in pr.get("title", "").lower():
                continue

            valid_prs.append({
                "id": pr.get("number"),
                "title": pr.get("title"),
                "body": (pr.get("body") or "Sin descripción proporcionada.")[:2000],
                "merged_at": pr.get("merged_at"),
                "url": pr.get("html_url"),
                "_raw_payload": pr,
            })
            
        return valid_prs