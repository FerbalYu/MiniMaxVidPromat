import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .jobs import job_store
from .minimax_client import MiniMaxClient
from .schemas import CreateJobResponse, JobActionResponse, JobPublic, JobRecord, JobStatus, PromptMode

settings = get_settings()
job_store.configure(settings.database_path)
UPLOAD_CHUNK_SIZE = 1024 * 1024
executor = ThreadPoolExecutor(max_workers=max(1, settings.max_concurrent_jobs))
job_futures: dict[str, Future] = {}
job_futures_lock = threading.Lock()

app = FastAPI(title="Video Prompt Local Server", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "model": settings.minimax_model,
        "files_api_enabled": settings.minimax_enable_files_api,
        "max_upload_mb": _max_upload_size_mb(),
        "max_concurrent_jobs": max(1, settings.max_concurrent_jobs),
        "job_retention_hours": settings.job_retention_hours,
    }


@app.post("/api/jobs", response_model=CreateJobResponse)
async def create_job(
    video: UploadFile = File(...),
    prompt_mode: PromptMode = Form(PromptMode.standard),
    language: str = Form("zh"),
) -> CreateJobResponse:
    job_store.cleanup_finished(older_than_seconds=settings.job_retention_hours * 60 * 60)
    if not video.filename:
        raise HTTPException(status_code=400, detail="缺少视频文件名")
    suffix = Path(video.filename).suffix.lower()
    if suffix not in {".mp4", ".avi", ".mov", ".mkv"}:
        raise HTTPException(status_code=400, detail="仅支持 MP4、AVI、MOV、MKV 视频")

    safe_name = Path(video.filename).name
    temp_path = settings.upload_dir / f"upload-{uuid4().hex}-{safe_name}"
    max_size_bytes = _max_upload_size_bytes()
    size_bytes = 0
    try:
        with temp_path.open("wb") as buffer:
            while chunk := await video.read(UPLOAD_CHUNK_SIZE):
                size_bytes += len(chunk)
                if size_bytes > max_size_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"视频不能超过 {_max_upload_size_mb()}MB；请压缩后重试。",
                    )
                buffer.write(chunk)
    except HTTPException:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        await video.close()
    if size_bytes == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="视频文件为空")

    job = job_store.create(
        filename=safe_name,
        size_bytes=size_bytes,
        path=temp_path,
        prompt_mode=prompt_mode,
        language=language,
    )
    final_path = settings.upload_dir / f"{job.id}{suffix}"
    temp_path.replace(final_path)
    job_store.update(job.id, meta={"path": str(final_path), "submitted_at": job.created_at})
    submit_job(job.id)
    return CreateJobResponse(job_id=job.id, status=job.status)


@app.get("/api/jobs/{job_id}", response_model=JobPublic)
def get_job(job_id: str) -> JobPublic:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _to_public_job(job)


@app.get("/api/jobs", response_model=list[JobPublic])
def list_jobs() -> list[JobPublic]:
    return [_to_public_job(job) for job in job_store.list_recent()]


@app.post("/api/jobs/{job_id}/cancel", response_model=JobActionResponse)
def cancel_job(job_id: str) -> JobActionResponse:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status == JobStatus.completed:
        return JobActionResponse(job_id=job_id, status=job.status, message="任务已完成")
    if job.status == JobStatus.failed:
        return JobActionResponse(job_id=job_id, status=job.status, message="任务已失败")
    if job.status == JobStatus.canceled:
        return JobActionResponse(job_id=job_id, status=job.status, message="任务已取消")

    with job_futures_lock:
        future = job_futures.get(job_id)
        canceled_future = future.cancel() if future else False
    if job.status == JobStatus.processing and not canceled_future:
        raise HTTPException(status_code=409, detail="任务正在处理，当前不能安全取消")

    job_store.delete_file(job)
    updated = job_store.update(
        job_id,
        status=JobStatus.canceled,
        progress=100,
        message="任务已取消",
        error="任务已取消",
    )
    return JobActionResponse(job_id=job_id, status=updated.status if updated else JobStatus.canceled, message="任务已取消")


@app.post("/api/jobs/{job_id}/retry", response_model=CreateJobResponse)
def retry_job(job_id: str) -> CreateJobResponse:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status not in {JobStatus.failed, JobStatus.canceled}:
        raise HTTPException(status_code=409, detail="仅失败或已取消任务可重试")
    video_path = job_store.get_path(job_id)
    if not video_path or not video_path.exists():
        raise HTTPException(status_code=410, detail="原始视频已清理，请重新上传")
    job_store.update(job_id, status=JobStatus.queued, progress=0, message="已重新提交，等待处理", error="")
    submit_job(job_id)
    return CreateJobResponse(job_id=job_id, status=JobStatus.queued)


@app.post("/api/jobs/cleanup")
def cleanup_jobs() -> dict:
    removed = job_store.cleanup_finished(older_than_seconds=settings.job_retention_hours * 60 * 60)
    return {"removed": removed}


def submit_job(job_id: str) -> None:
    future = executor.submit(process_job, job_id)
    with job_futures_lock:
        job_futures[job_id] = future


def process_job(job_id: str) -> None:
    job = job_store.get(job_id)
    if not job:
        return
    if job.status == JobStatus.canceled:
        return
    video_path_str = job.meta.get("path")
    video_path = Path(video_path_str) if video_path_str else job_store.get_path(job_id)
    if not video_path or not video_path.exists():
        job_store.update(
            job_id,
            status=JobStatus.failed,
            progress=100,
            message="视频文件不存在",
            error="视频文件不存在",
        )
        return
    try:
        current = job_store.get(job_id)
        if current and current.status == JobStatus.canceled:
            return
        job_store.update(job_id, status=JobStatus.processing, progress=20, message="正在准备 MiniMax 请求")
        client = MiniMaxClient(settings)
        job_store.update(job_id, progress=45, message="正在调用 MiniMax-M3 识别视频")
        result = client.analyze_video(video_path, prompt_mode=job.prompt_mode, language=job.language)
        job_store.update(
            job_id,
            status=JobStatus.completed,
            progress=100,
            message="提示词生成完成",
            result=result,
        )
    except Exception as exc:
        job_store.update(
            job_id,
            status=JobStatus.failed,
            progress=100,
            message="处理失败",
            error=str(exc),
        )
    finally:
        with job_futures_lock:
            job_futures.pop(job_id, None)
        if video_path and video_path.exists():
            video_path.unlink(missing_ok=True)


def _max_upload_size_mb() -> int:
    if settings.minimax_enable_files_api:
        return settings.max_upload_mb
    return settings.minimax_max_base64_mb


def _max_upload_size_bytes() -> int:
    return _max_upload_size_mb() * 1024 * 1024


def _to_public_job(job: JobRecord) -> JobPublic:
    payload = job.model_dump()
    payload["meta"] = {key: value for key, value in job.meta.items() if key != "path"}
    return JobPublic(**payload)


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
