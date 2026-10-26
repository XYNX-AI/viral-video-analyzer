from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env",
        extra="ignore",
    )

    # OpenAI-compatible model settings.  The base URL can point to OpenAI or
    # another compatible provider without changing the analysis services.
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_VISION_MODEL: str = "gpt-4o-mini"
    DATA_DIR: str = "data"
    DOUYIN_COOKIE_FILE: str = ""
    # Optional Netscape cookie file used by yt-dlp for overseas platforms.
    YTDLP_COOKIE_FILE: str = ""
    # Optional per-platform yt-dlp cookie files. Format: platform=/path/file,platform2=/path/file2
    YTDLP_COOKIE_FILES: str = ""
    YTDLP_BIN: str = "yt-dlp"
    YTDLP_PROXY: str = ""
    # faster-whisper model size: tiny/base/small/medium/large-v3.
    WHISPER_MODEL: str = "small"
    # Delete the downloaded video right after frame/audio extraction, and the
    # extracted audio right after transcription, to keep disk usage flat.
    DELETE_MEDIA_AFTER_USE: bool = True
    # Opt-in cleanup after the full pipeline finishes. When enabled, frames
    # and any remaining media are removed while result.json/result.xlsx stay.
    DELETE_INTERMEDIATE_MEDIA_AFTER_ANALYSIS: bool = False

settings = Settings()
