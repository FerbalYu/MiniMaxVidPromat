import threading
import time
from pathlib import Path
from uuid import uuid4

from .schemas import JobRecord, JobStatus, PromptMode, PromptResult


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._paths: dict[str, Path] = {}
        self._lock = threading.Lock()

    def create(self, *, filename: str, size_bytes: int, path: Path, prompt_mode: PromptMode, language: str) -> JobRecord:
        now = time.time()
        job = JobRecord(
            id=uuid4().hex,
            filename=filename,
            size_bytes=size_bytes,
            prompt_mode=prompt_mode,
            language=language,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[job.id] = job
            self._paths[job.id] = path
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get_path(self, job_id: str) -> Path | None:
        with self._lock:
            return self._paths.get(job_id)

    def list_recent(self, limit: int = 20) -> list[JobRecord]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
        return jobs[:limit]

    def update(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        progress: int | None = None,
        message: str | None = None,
        result: PromptResult | None = None,
        error: str | None = None,
        meta: dict | None = None,
    ) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            updates = {
                "updated_at": time.time(),
            }
            if status is not None:
                updates["status"] = status
            if progress is not None:
                updates["progress"] = max(0, min(100, progress))
            if message is not None:
                updates["message"] = message
            if result is not None:
                updates["result"] = result
            if error is not None:
                updates["error"] = error
            if meta is not None:
                updates["meta"] = {**job.meta, **meta}
            updated = job.model_copy(update=updates)
            self._jobs[job_id] = updated
            return updated


job_store = JobStore()

