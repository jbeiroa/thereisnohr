import requests
import time
from typing import Any, Dict, List, Optional

class APIClient:
    def __init__(self, base_url: str = "http://localhost:8000/api"):
        self.base_url = base_url

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        response = requests.get(f"{self.base_url}/{endpoint}", params=params, timeout=120.0)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, json_data: Optional[Dict] = None) -> Any:
        response = requests.post(f"{self.base_url}/{endpoint}", json=json_data, timeout=120.0)
        response.raise_for_status()
        return response.json()

    # Tasks
    def get_task(self, task_id: int) -> Dict:
        return self._get(f"tasks/{task_id}")

    def poll_task(self, task_id: int, interval: float = 2.0, timeout: int = 300) -> Dict:
        start_time = time.time()
        while time.time() - start_time < timeout:
            task = self.get_task(task_id)
            if task["status"] in ["COMPLETED", "FAILED"]:
                return task
            time.sleep(interval)
        raise TimeoutError(f"Task {task_id} timed out after {timeout} seconds")

    # Jobs
    def list_jobs(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        return self._get("jobs/", params={"skip": skip, "limit": limit})

    def get_job(self, job_id: int) -> Dict:
        return self._get(f"jobs/{job_id}")

    def create_job(self, title: str, description: str) -> Dict:
        return self._post("jobs/", json_data={"title": title, "description": description})

    def rank_job(self, job_id: int, top_k: int = 5) -> Dict:
        return self._post(f"jobs/{job_id}/rank", json_data={"top_k": top_k})

    # Candidates
    def list_candidates(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        return self._get("candidates/", params={"skip": skip, "limit": limit})

    def get_candidate(self, candidate_id: int) -> Dict:
        return self._get(f"candidates/{candidate_id}")

    # Ingest
    def ingest_resumes(self, input_dir: str, pattern: str = "*.pdf") -> Dict:
        return self._post("ingest/resumes", json_data={"input_dir": input_dir, "pattern": pattern})

    def upload_resumes(self, files: List[Any]) -> Dict:
        if not files:
            raise ValueError("No files provided for upload")

        payload = []
        for file in files:
            # We must use 'files' as the field name to match backend: list[UploadFile] = File(...)
            payload.append(("files", (file.name, file.getvalue(), "application/pdf")))
        
        url = f"{self.base_url}/ingest/upload"
        try:
            response = requests.post(url, files=payload, timeout=120.0)
            if response.status_code != 200:
                try:
                    detail = response.json().get("detail", response.text)
                except:
                    detail = response.text
                raise Exception(f"Upload failed ({response.status_code}) at {url}: {detail}")
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Connection error to {url}: {e}")

    # Matches
    def list_matches(self, job_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[Dict]:
        params = {"skip": skip, "limit": limit}
        if job_id:
            params["job_id"] = job_id
        return self._get("matches/", params=params)

    def get_match(self, match_id: int) -> Dict:
        return self._get(f"matches/{match_id}")

    def generate_prep(self, match_id: int) -> Dict:
        return self._post(f"matches/{match_id}/prep")
