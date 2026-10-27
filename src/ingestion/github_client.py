import requests
from src.config import GITHUB_TOKEN


class GitHubAPIError(RuntimeError):
    """Error al consultar la API de GitHub."""


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self):
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if GITHUB_TOKEN:
            self.headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    def _get(self, url: str, **kwargs) -> requests.Response:
        try:
            response = requests.get(url, headers=self.headers, **kwargs)
        except requests.RequestException as error:
            raise GitHubAPIError("No se pudo conectar con GitHub.") from error

        if response.status_code == 401 and "Authorization" in self.headers:
            try:
                response = requests.get(
                    url,
                    headers={"Accept": "application/vnd.github.v3+json"},
                    **kwargs,
                )
            except requests.RequestException as error:
                raise GitHubAPIError("No se pudo conectar con GitHub.") from error
        return response

    def fetch_closed_prs(self, repo: str, limit: int = 20) -> list[dict]:
        url = f"{self.BASE_URL}/repos/{repo}/pulls"
        params = {"state": "closed", "per_page": limit}
        
        response = self._get(url, params=params, timeout=15)
        if response.status_code != 200:
            raise GitHubAPIError(
                f"GitHub respondió {response.status_code} al consultar {repo}: "
                f"{response.text[:200]}"
            )

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

    def get_repository_full_name(self, repo: str) -> str:
        response = self._get(f"{self.BASE_URL}/repos/{repo}", timeout=15)
        if response.status_code == 404:
            raise GitHubAPIError("Repositorio no encontrado en GitHub.")
        if not response.ok:
            raise GitHubAPIError(
                f"GitHub respondió {response.status_code} al validar {repo}: "
                f"{response.text[:200]}"
            )

        full_name = response.json().get("full_name")
        if not full_name:
            raise GitHubAPIError("GitHub no devolvió el nombre del repositorio.")
        return full_name

    def repository_exists(self, repo: str) -> bool:
        response = self._get(f"{self.BASE_URL}/repos/{repo}", timeout=15)

        if response.status_code == 404:
            return False

        if not response.ok:
            raise GitHubAPIError(
                f"GitHub respondió {response.status_code} al validar {repo}: "
                f"{response.text[:200]}"
            )
        return True