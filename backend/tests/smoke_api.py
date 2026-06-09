from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app import main
from app.minimax_client import parse_prompt_result
from app.schemas import PromptResult


test_root = Path(tempfile.mkdtemp(prefix="minimaxvidpromat-smoke-"))
main.settings.upload_dir = test_root / "uploads"
main.settings.result_dir = test_root / "results"
main.settings.database_path = test_root / "jobs.sqlite"
main.settings.upload_dir.mkdir(parents=True, exist_ok=True)
main.settings.result_dir.mkdir(parents=True, exist_ok=True)
main.job_store.configure(main.settings.database_path)

client = TestClient(main.app)


def assert_response(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_health() -> None:
    response = client.get("/api/health")
    assert_response(response.status_code == 200, "health should return 200")
    payload = response.json()
    assert_response(payload["ok"] is True, "health ok should be true")
    assert_response("model" in payload, "health should expose model")


def test_reject_invalid_extension() -> None:
    response = client.post(
        "/api/jobs",
        files={"video": ("clip.txt", b"hello", "text/plain")},
        data={"prompt_mode": "standard", "language": "zh"},
    )
    assert_response(response.status_code == 400, "invalid extension should return 400")


def test_reject_empty_video() -> None:
    response = client.post(
        "/api/jobs",
        files={"video": ("empty.mp4", b"", "video/mp4")},
        data={"prompt_mode": "standard", "language": "zh"},
    )
    assert_response(response.status_code == 400, "empty video should return 400")


def test_reject_oversize_video_without_full_write() -> None:
    original_limit = main.settings.minimax_max_base64_mb
    main.settings.minimax_max_base64_mb = 0
    try:
        response = client.post(
            "/api/jobs",
            files={"video": ("big.mp4", b"x", "video/mp4")},
            data={"prompt_mode": "standard", "language": "zh"},
        )
        assert_response(response.status_code == 413, "oversize video should return 413")
    finally:
        main.settings.minimax_max_base64_mb = original_limit


def test_public_job_does_not_expose_local_path() -> None:
    original_submit = main.submit_job
    main.submit_job = lambda job_id: None
    response = client.post(
        "/api/jobs",
        files={"video": ("small.mp4", b"fake-video", "video/mp4")},
        data={"prompt_mode": "standard", "language": "zh"},
    )
    try:
        assert_response(response.status_code == 200, "small video should create a job")
        job_id = response.json()["job_id"]

        detail = client.get(f"/api/jobs/{job_id}")
        assert_response(detail.status_code == 200, "created job should be readable")
        payload = detail.json()
        assert_response("path" not in payload.get("meta", {}), "public meta must not expose local path")
    finally:
        main.submit_job = original_submit

        for path in Path(main.settings.upload_dir).glob(f"{response.json().get('job_id', '')}.*"):
            path.unlink(missing_ok=True)


def test_process_job_success_and_cleanup() -> None:
    original_client = main.MiniMaxClient

    class FakeMiniMaxClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        def analyze_video(self, video_path: Path, *, prompt_mode, language) -> PromptResult:
            return PromptResult(summary="ok", seedance_prompt="生成成功")

    main.MiniMaxClient = FakeMiniMaxClient
    video_path = main.settings.upload_dir / "success.mp4"
    video_path.write_bytes(b"fake-video")
    job = main.job_store.create(
        filename="success.mp4",
        size_bytes=video_path.stat().st_size,
        path=video_path,
        prompt_mode=main.PromptMode.standard,
        language="zh",
    )
    try:
        main.process_job(job.id)
        updated = main.job_store.get(job.id)
        assert_response(updated is not None and updated.status == main.JobStatus.completed, "job should complete")
        assert_response(updated.result is not None and updated.result.seedance_prompt == "生成成功", "result should be saved")
        assert_response(not video_path.exists(), "processed video should be deleted")
    finally:
        main.MiniMaxClient = original_client


def test_process_job_failure_and_cleanup() -> None:
    original_client = main.MiniMaxClient

    class FailingMiniMaxClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        def analyze_video(self, video_path: Path, *, prompt_mode, language) -> PromptResult:
            raise RuntimeError("fake minimax failure")

    main.MiniMaxClient = FailingMiniMaxClient
    video_path = main.settings.upload_dir / "failure.mp4"
    video_path.write_bytes(b"fake-video")
    job = main.job_store.create(
        filename="failure.mp4",
        size_bytes=video_path.stat().st_size,
        path=video_path,
        prompt_mode=main.PromptMode.standard,
        language="zh",
    )
    try:
        main.process_job(job.id)
        updated = main.job_store.get(job.id)
        assert_response(updated is not None and updated.status == main.JobStatus.failed, "job should fail")
        assert_response("fake minimax failure" in (updated.error or ""), "failure should be recorded")
        assert_response(not video_path.exists(), "failed video should be deleted")
    finally:
        main.MiniMaxClient = original_client


def test_parse_prompt_result_handles_noisy_json() -> None:
    result = parse_prompt_result(
        """```json
        {
          "result": {
            "summary": "一段实拍视频",
            "subject": ["人物", "红色外套"],
            "seedance_prompt": "真实视频复现提示词"
          }
        }
        ```"""
    )
    assert_response(result.summary == "一段实拍视频", "parser should read fenced nested JSON")
    assert_response("红色外套" in result.subject, "parser should stringify list fields")
    assert_response(result.seedance_prompt == "真实视频复现提示词", "parser should keep prompt field")


def main_test() -> None:
    test_health()
    test_reject_invalid_extension()
    test_reject_empty_video()
    test_reject_oversize_video_without_full_write()
    test_public_job_does_not_expose_local_path()
    test_process_job_success_and_cleanup()
    test_process_job_failure_and_cleanup()
    test_parse_prompt_result_handles_noisy_json()
    print("backend smoke tests passed")


if __name__ == "__main__":
    main_test()
