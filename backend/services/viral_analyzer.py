import asyncio
import functools
import json

import httpx
from openai import OpenAI
from pydantic import ValidationError

from config import settings
from models.schemas import VideoMeta, ViralAnalysis


VIRAL_ANALYSIS_SYSTEM = """你是一位专业的短视频内容分析师，擅长拆解带货和种草类短视频的结构。

请根据视频元信息、完整口播文案和按时间排列的画面分析，严格输出一个有效 JSON 对象。不要输出 Markdown、解释或 JSON 代码块。无法从输入确定的字段必须填写“未明确”，不要臆测。

JSON 必须包含且只能优先使用以下字段：
{
  "hook": "前几秒如何让用户停下来，引用具体文案或画面证据",
  "pain_point": "描述消费者遇到的具体问题",
  "demonstration": "产品何时出场，以及如何展示功能或使用方式",
  "proof": "如何证明产品解决了问题，例如演示、对比、数据或用户反馈",
  "cta": "结尾如何推动用户购买或采取行动",
  "usage_scenario": "产品的使用场景",
  "person": "出镜人物及其角色",
  "product_appearance_time": "产品首次出现的时间点或时间段",
  "before_after": "使用前后的状态对比；没有证据则为未明确",
  "video_duration": "视频时长",
  "visual_structure": "画面结构和段落节奏",
  "voiceover": "口播内容的作用、语气和节奏",
  "caption": "字幕或画面文字的内容及作用"
}

要求：
- 同时结合口播文案和画面描述，不要只复述其中一项
- 时间点使用输入中的时间信息，无法定位时写“未明确”
- 输出内容要清晰、具体、可直接用于复盘和创作"""


def _get_client() -> OpenAI:
    return OpenAI(
        base_url=settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
        http_client=httpx.Client(trust_env=False),
    )


def _analyze_viral_sync(
    meta: VideoMeta,
    full_transcript: str,
    segments_summary: str,
) -> ViralAnalysis:
    """Synchronous viral analysis (runs in thread pool)."""
    client = _get_client()

    likes_str = f"{meta.likes}" if meta.likes else "未知"
    comments_str = f"{meta.comments}" if meta.comments else "未知"
    shares_str = f"{meta.shares}" if meta.shares else "未知"

    user_content = f"""视频信息：
- 标题：{meta.title}
- 作者：{meta.author}
- 点赞数：{likes_str}
- 评论数：{comments_str}
- 分享数：{shares_str}
- 时长：{meta.duration:.1f}秒

完整口播/字幕文案：
{full_transcript or '（无语音内容）'}

逐秒画面分析摘要：
{segments_summary}

请深入分析这条视频的爆款密码。"""

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": VIRAL_ANALYSIS_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0.5,
        max_tokens=2000,
    )

    raw = (response.choices[0].message.content or "").strip()
    raw = _extract_json(raw)

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ViralAnalysis(
            hook_score=0,
            hook_analysis=raw[:500],
        )

    # Keep old consumers working while exposing the new structure.
    if isinstance(data, dict):
        data.setdefault("hook_analysis", data.get("hook", ""))
        data.setdefault("content_formula", data.get("visual_structure", ""))
        data.setdefault("target_audience", data.get("usage_scenario", ""))
        data.setdefault("recreation_blueprint", data.get("demonstration", ""))
    try:
        return ViralAnalysis.model_validate(data)
    except (TypeError, ValidationError):
        return ViralAnalysis(
            hook_score=0,
            hook_analysis=raw[:500],
        )


def _extract_json(raw: str) -> str:
    """Remove code fences and isolate a JSON object from a chat response."""
    if raw.startswith("```"):
        parts = raw.split("```", 2)
        raw = parts[1] if len(parts) > 1 else raw
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]

    raw = raw.strip()
    if not raw.startswith("{"):
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
    return raw.strip()


async def analyze_viral(
    meta: VideoMeta,
    full_transcript: str,
    segments_summary: str,
) -> ViralAnalysis:
    """Async wrapper for viral analysis."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        functools.partial(_analyze_viral_sync, meta, full_transcript, segments_summary),
    )
