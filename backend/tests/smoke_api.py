from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app import main
from app.minimax_client import parse_prompt_result


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
    response = client.post(
        "/api/jobs",
        files={"video": ("small.mp4", b"fake-video", "video/mp4")},
        data={"prompt_mode": "standard", "language": "zh"},
    )
    assert_response(response.status_code == 200, "small video should create a job")
    job_id = response.json()["job_id"]

    detail = client.get(f"/api/jobs/{job_id}")
    assert_response(detail.status_code == 200, "created job should be readable")
    payload = detail.json()
    assert_response("path" not in payload.get("meta", {}), "public meta must not expose local path")

    for path in Path(main.settings.upload_dir).glob(f"{job_id}.*"):
        path.unlink(missing_ok=True)


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
    test_parse_prompt_result_handles_noisy_json()
    print("backend smoke tests passed")


if __name__ == "__main__":
    main_test()
