from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.minimax_client import MiniMaxClient
from app.schemas import PromptMode


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python tests/manual_real_api.py <video-path>")
    video_path = Path(sys.argv[1]).resolve()
    if not video_path.exists():
        raise SystemExit(f"Video not found: {video_path}")

    settings = get_settings()
    client = MiniMaxClient(settings)
    result = client.analyze_video(video_path, prompt_mode=PromptMode.standard, language="zh")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
