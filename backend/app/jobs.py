import json
import sqlite3
import threading
import time
from pathlib import Path
from uuid import uuid4

from .schemas import JobRecord, JobStatus, PromptMode, PromptResult


class JobStore:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or Path("./storage/jobs.sqlite")
        self._lock = threading.Lock()
        self._initialized = False

    def configure(self, database_path: Path) -> None:
        with self._lock:
            self.database_path = database_path
            self._initialized = False
            self._ensure_initialized()

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
            meta={"path": str(path)},
        )
        with self._lock, self._connect() as conn:
            self._insert_job(conn, job)
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def get_path(self, job_id: str) -> Path | None:
        job = self.get(job_id)
        if not job:
            return None
        value = job.meta.get("path")
        return Path(str(value)) if value else None

    def list_recent(self, limit: int = 20) -> list[JobRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

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
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return None
            job = self._row_to_job(row)
            updates = {
                "status": status.value if status is not None else job.status.value,
                "progress": max(0, min(100, progress)) if progress is not None else job.progress,
                "message": message if message is not None else job.message,
                "result_json": self._dump_result(result if result is not None else job.result),
                "error": error if error is not None else job.error,
                "meta_json": self._dump_json({**job.meta, **meta}) if meta is not None else self._dump_json(job.meta),
                "updated_at": time.time(),
                "id": job_id,
            }
            conn.execute(
                """
                UPDATE jobs
                SET status = :status,
                    progress = :progress,
                    message = :message,
                    result_json = :result_json,
                    error = :error,
                    meta_json = :meta_json,
                    updated_at = :updated_at
                WHERE id = :id
                """,
                updates,
            )
            conn.commit()
        return self.get(job_id)

    def cleanup_finished(self, *, older_than_seconds: int) -> int:
        cutoff = time.time() - older_than_seconds
        statuses = (JobStatus.completed.value, JobStatus.failed.value, JobStatus.canceled.value)
        removed = 0
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE updated_at < ? AND status IN (?, ?, ?)",
                (cutoff, *statuses),
            ).fetchall()
            for row in rows:
                job = self._row_to_job(row)
                self.delete_file(job)
                conn.execute("DELETE FROM jobs WHERE id = ?", (job.id,))
                removed += 1
            conn.commit()
        return removed

    def delete_file(self, job: JobRecord) -> None:
        value = job.meta.get("path")
        if value:
            Path(str(value)).unlink(missing_ok=True)

    def _connect(self) -> sqlite3.Connection:
        self._ensure_initialized()
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    prompt_mode TEXT NOT NULL,
                    language TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    meta_json TEXT NOT NULL
                )
                """
            )
            conn.commit()
        self._initialized = True

    def _insert_job(self, conn: sqlite3.Connection, job: JobRecord) -> None:
        conn.execute(
            """
            INSERT INTO jobs (
                id, status, filename, size_bytes, prompt_mode, language, progress,
                message, result_json, error, created_at, updated_at, meta_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.status.value,
                job.filename,
                job.size_bytes,
                job.prompt_mode.value,
                job.language,
                job.progress,
                job.message,
                self._dump_result(job.result),
                job.error,
                job.created_at,
                job.updated_at,
                self._dump_json(job.meta),
            ),
        )
        conn.commit()

    def _row_to_job(self, row: sqlite3.Row) -> JobRecord:
        result = None
        if row["result_json"]:
            result = PromptResult(**json.loads(row["result_json"]))
        return JobRecord(
            id=row["id"],
            status=JobStatus(row["status"]),
            filename=row["filename"],
            size_bytes=row["size_bytes"],
            prompt_mode=PromptMode(row["prompt_mode"]),
            language=row["language"],
            progress=row["progress"],
            message=row["message"],
            result=result,
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            meta=json.loads(row["meta_json"] or "{}"),
        )

    def _dump_result(self, result: PromptResult | None) -> str | None:
        return json.dumps(result.model_dump(), ensure_ascii=False) if result else None

    def _dump_json(self, payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False)


job_store = JobStore()
