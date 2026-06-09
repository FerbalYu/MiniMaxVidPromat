import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI

from .config import Settings
from .schemas import PromptMode, PromptResult


MODE_LABELS = {
    PromptMode.standard: "通用写实视频",
    PromptMode.cinematic: "电影感与运镜强化",
    PromptMode.product: "商品展示与商业广告",
    PromptMode.short_drama: "短剧剧情与人物动作",
}


class MiniMaxClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.minimax_api_key:
            raise RuntimeError("缺少 MINIMAX_API_KEY，请在 backend/.env 中配置 MiniMax API Key。")
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.minimax_api_key,
            base_url=settings.minimax_base_url,
            timeout=settings.minimax_request_timeout_seconds,
        )

    def analyze_video(self, video_path: Path, *, prompt_mode: PromptMode, language: str) -> PromptResult:
        video_url = self._build_video_url(video_path)
        fact_content = self._create_json_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "你是严谨的视频事实分析器。只记录视频中能观察到的事实，"
                        "不要补写品牌、地点、身份或未出现的元素。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self._build_fact_prompt()},
                        {
                            "type": "video_url",
                            "video_url": {
                                "url": video_url,
                                "detail": "default",
                                "fps": 1,
                            },
                        },
                    ],
                },
            ],
            max_tokens=2000,
        )
        facts = _parse_json_object(fact_content)
        if self.settings.minimax_repair_json and "raw_text" in facts:
            facts = _parse_json_object(self._repair_json(fact_content, target="video facts"))

        prompt_content = self._create_json_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "你是视频生成提示词工程专家，专门把视频事实改写为即梦/Seedance 2.0 "
                        "可直接使用的提示词。必须忠于事实，不要添加视频中不存在的主体。"
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_prompt(
                        prompt_mode=prompt_mode,
                        language=language,
                        facts=facts,
                    ),
                },
            ],
            max_tokens=3500,
        )
        result = parse_prompt_result(prompt_content)
        if self.settings.minimax_repair_json and not result.seedance_prompt:
            repaired = self._repair_json(prompt_content, target="final prompt result")
            result = parse_prompt_result(repaired)
        if result.raw_text == prompt_content:
            result.raw_text = json.dumps({"facts": facts, "prompt_result": prompt_content}, ensure_ascii=False)
        return result

    def _create_json_completion(self, messages: list[dict[str, Any]], *, max_tokens: int) -> str:
        response = self.client.chat.completions.create(
            model=self.settings.minimax_model,
            messages=messages,
            max_completion_tokens=max_tokens,
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "disabled"}},
        )
        return response.choices[0].message.content or ""

    def _repair_json(self, content: str, *, target: str) -> str:
        return self._create_json_completion(
            [
                {
                    "role": "system",
                    "content": "你是 JSON 修复器。只输出一个合法 JSON 对象，不输出 Markdown 或解释。",
                },
                {
                    "role": "user",
                    "content": (
                        f"请把下面的 {target} 修复为合法 JSON 对象，保留所有可用信息，"
                        f"缺失字段用空字符串：\n{content}"
                    ),
                },
            ],
            max_tokens=2500,
        )

    def _build_video_url(self, video_path: Path) -> str:
        size_mb = video_path.stat().st_size / 1024 / 1024
        if size_mb <= self.settings.minimax_max_base64_mb:
            media_type = mimetypes.guess_type(video_path.name)[0] or "video/mp4"
            data = base64.b64encode(video_path.read_bytes()).decode("ascii")
            return f"data:{media_type};base64,{data}"
        if self.settings.minimax_enable_files_api:
            file_id = self._upload_file(video_path)
            return f"mm_file://{file_id}"
        raise RuntimeError(
            f"视频大小为 {size_mb:.1f}MB，超过当前 base64 阈值 {self.settings.minimax_max_base64_mb}MB。"
            "请压缩视频，或开启 MINIMAX_ENABLE_FILES_API=true。"
        )

    def _upload_file(self, video_path: Path) -> str:
        # MiniMax 文档允许视频通过 mm_file://file_id 输入。purpose 在不同业务线可能变化，
        # 所以这里暴露为 MINIMAX_FILE_PURPOSE，避免写死后续不可用。
        upload_url = f"{self.settings.minimax_base_url.rstrip('/')}/files"
        headers = {"Authorization": f"Bearer {self.settings.minimax_api_key}"}
        with video_path.open("rb") as file_obj:
            files = {"file": (video_path.name, file_obj, mimetypes.guess_type(video_path.name)[0] or "video/mp4")}
            data = {"purpose": self.settings.minimax_file_purpose}
            response = httpx.post(upload_url, headers=headers, data=data, files=files, timeout=120)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        file_id = payload.get("id") or payload.get("file_id")
        if not file_id:
            raise RuntimeError(f"MiniMax Files API 未返回 file_id：{payload}")
        return str(file_id)

    def _build_fact_prompt(self) -> str:
        return """
请分析这个视频，只输出 JSON，字段如下：
{
  "summary": "视频事实摘要，50-120字",
  "subjects": ["主体列表，包括人物/物体/服饰/外观"],
  "scene": "场景与环境",
  "actions": ["动作过程与节奏"],
  "camera": "运镜、景别、机位、镜头运动",
  "lighting": "光线、色彩、氛围",
  "style": "画面风格、质感、清晰度",
  "visible_text": ["视频中真实可见文字，没有则为空数组"],
  "uncertainties": ["无法确定但影响提示词的点，没有则为空数组"]
}

要求：
1. 只写视频中可观察的事实。
2. 不要推断品牌、地点、身份、时代背景。
3. 不要输出 Markdown，不要在 JSON 外输出解释。
""".strip()

    def _build_prompt(self, *, prompt_mode: PromptMode, language: str, facts: dict[str, Any]) -> str:
        mode_label = MODE_LABELS.get(prompt_mode, MODE_LABELS[PromptMode.standard])
        output_language = "中文为主，英文版单独给出" if language == "zh" else "英文为主，中文版可简短给出"
        return f"""
请根据下面的视频事实 JSON，把它转换成适合即梦/Seedance 2.0 的视频生成提示词。

目标风格：{mode_label}
输出语言：{output_language}

视频事实 JSON：
{json.dumps(facts, ensure_ascii=False)}

请严格输出 JSON，字段如下：
{{
  "summary": "视频内容摘要，50-120字",
  "subject": "主体，包括人物/物体/服饰/外观",
  "scene": "场景与环境",
  "action": "动作过程与节奏",
  "camera": "运镜、景别、机位、镜头运动",
  "lighting": "光线、色彩、氛围",
  "style": "画面风格、质感、清晰度",
  "seedance_prompt": "即梦一键粘贴版中文提示词，180-350字，连续自然语言",
  "storyboard_prompt": "分镜增强版，按镜头1/镜头2/镜头3组织",
  "negative_prompt": "负面提示词，避免畸形、闪烁、文字水印、脸部崩坏等",
  "english_prompt": "英文提示词版本"
}}

要求：
1. 只能基于视频事实 JSON，不要虚构不存在的主体、品牌、文字。
2. seedance_prompt 必须包含主体、场景、动作、运镜、光线、风格、画质、节奏。
3. 如果视频像实拍素材，优先写成可复现原视频的提示词。
4. 如果有明显镜头运动，请具体描述为推进、跟拍、环绕、摇镜、俯拍、低机位等。
5. 不要输出 Markdown，不要在 JSON 外输出解释。
""".strip()


def parse_prompt_result(content: str) -> PromptResult:
    data = _parse_json_object(content)
    return PromptResult(
        summary=_stringify_field(data.get("summary", "")),
        subject=_stringify_field(data.get("subject", "")),
        scene=_stringify_field(data.get("scene", "")),
        action=_stringify_field(data.get("action", "")),
        camera=_stringify_field(data.get("camera", "")),
        lighting=_stringify_field(data.get("lighting", "")),
        style=_stringify_field(data.get("style", "")),
        seedance_prompt=_stringify_field(data.get("seedance_prompt", "")),
        storyboard_prompt=_stringify_field(data.get("storyboard_prompt", "")),
        negative_prompt=_stringify_field(data.get("negative_prompt", "")),
        english_prompt=_stringify_field(data.get("english_prompt", "")),
        raw_text=str(data.get("raw_text", content)),
    )


def _parse_json_object(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    for candidate in (cleaned, _extract_json_object(cleaned)):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            nested = data.get("result")
            if isinstance(nested, dict):
                return nested
            return data
    return {"raw_text": content}


def _extract_json_object(content: str) -> str:
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        return content[start : end + 1]
    return ""


def _stringify_field(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
