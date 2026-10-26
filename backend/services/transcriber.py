import asyncio
import functools
import os
import threading

from config import settings
from models.schemas import TranscriptSegment, TranscriptWord

# Whisper reloads the model on every call, and each load without
# local_files_only performs a HuggingFace Hub lookup that takes ~135s on a
# China-based host. Keep one process-wide instance instead.
_MODEL = None
_MODEL_LOCK = threading.Lock()

# Whisper's Chinese output defaults to Traditional characters and mangles
# homophones ("爆款" -> "報款"). A simplified-Chinese prompt pins the script.
_PROMPT = "以下是普通话短视频的口语内容，请使用简体中文转写，并加上标点符号。"


def _get_model():
    """Load the Whisper model once per process and reuse it."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is None:
            from faster_whisper import WhisperModel

            kwargs = dict(
                device="cpu",
                compute_type="int8",
                cpu_threads=min(8, os.cpu_count() or 4),
            )
            try:
                # Fast path: no network round-trip to huggingface.co.
                _MODEL = WhisperModel(
                    settings.WHISPER_MODEL, local_files_only=True, **kwargs
                )
            except Exception:
                # First run on a fresh host: allow the download.
                _MODEL = WhisperModel(settings.WHISPER_MODEL, **kwargs)

    return _MODEL


def _run_whisper_sync(audio_path: str) -> list[TranscriptSegment]:
    """Synchronous Whisper transcription (runs in thread pool)."""
    model = _get_model()

    segments_iter, info = model.transcribe(
        audio_path,
        language="zh",
        word_timestamps=True,
        vad_filter=True,
        initial_prompt=_PROMPT,
        beam_size=5,
    )

    result = []
    for seg in segments_iter:
        words = []
        if seg.words:
            words = [
                TranscriptWord(word=w.word.strip(), start=w.start, end=w.end)
                for w in seg.words
                if w.word.strip()
            ]
        result.append(TranscriptSegment(
            text=seg.text.strip(),
            start=seg.start,
            end=seg.end,
            words=words,
        ))

    return result


async def transcribe_with_whisper(audio_path: str) -> list[TranscriptSegment]:
    """Async wrapper that runs Whisper in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        functools.partial(_run_whisper_sync, audio_path),
    )
