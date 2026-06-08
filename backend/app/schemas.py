from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class PromptMode(str, Enum):
    standard = "standard"
    cinematic = "cinematic"
    product = "product"
    short_drama = "short_drama"


class CreateJobResponse(BaseModel):
    job_id: str
    status: JobStatus


class PromptResult(BaseModel):
    summary: str = ""
    subject: str = ""
    scene: str = ""
    action: str = ""
    camera: str = ""
    lighting: str = ""
    style: str = ""
    seedance_prompt: str = ""
    storyboard_prompt: str = ""
    negative_prompt: str = ""
    english_prompt: str = ""
    raw_text: str = ""


class JobRecord(BaseModel):
    id: str
    status: JobStatus = JobStatus.queued
    filename: str
    size_bytes: int
    prompt_mode: PromptMode = PromptMode.standard
    language: str = "zh"
    progress: int = 0
    message: str = "等待处理"
    result: PromptResult | None = None
    error: str | None = None
    created_at: float
    updated_at: float
    meta: dict[str, Any] = Field(default_factory=dict)


class JobPublic(BaseModel):
    id: str
    status: JobStatus
    filename: str
    size_bytes: int
    prompt_mode: PromptMode
    language: str
    progress: int
    message: str
    result: PromptResult | None
    error: str | None
    created_at: float
    updated_at: float
    meta: dict[str, Any]

