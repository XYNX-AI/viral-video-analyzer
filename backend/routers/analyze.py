import asyncio
import json
import os
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from config import settings
from models.schemas import AnalyzeResponse
from services.pipeline import read_url_list, run_batch_pipeline, run_pipeline

router = APIRouter()

# In-memory task store
tasks: dict[str, dict] = {}


class AnalyzeRequest(BaseModel):
    url: str
    detail: Optional[dict] = None  # Allow frontend to pass pre-fetched detail JSON


class BatchAnalyzeRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)
    urls_file: Optional[str] = None  # One URL per line on the backend host


@router.post("/api/analyze", response_model=AnalyzeResponse)
async def start_analysis(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())[:8]
    event_queue = asyncio.Queue()
    tasks[task_id] = {
        "status": "queued",
        "events": event_queue,
    }

    # If detail JSON was provided, save it for the downloader
    if req.detail:
        task_dir = os.path.join(settings.DATA_DIR, task_id)
        os.makedirs(task_dir, exist_ok=True)
        detail_path = os.path.join(task_dir, "detail.json")
        with open(detail_path, "w", encoding="utf-8") as f:
            json.dump(req.detail, f, ensure_ascii=False)

    background_tasks.add_task(run_pipeline, task_id, req.url, event_queue)
    return AnalyzeResponse(task_id=task_id, status="queued")


@router.post("/api/analyze/batch", response_model=AnalyzeResponse)
async def start_batch_analysis(req: BatchAnalyzeRequest, background_tasks: BackgroundTasks):
    urls = [url.strip() for url in req.urls if url.strip()]
    if req.urls_file:
        try:
            urls.extend(read_url_list(req.urls_file))
        except (OSError, ValueError) as exc:
            raise HTTPException(400, f"读取链接列表失败: {exc}") from exc

    # Keep accidental submissions from creating an unbounded background job.
    if not urls:
        raise HTTPException(400, "至少提供一个视频链接或 urls_file")
    if len(urls) > 50:
        raise HTTPException(400, "单批最多支持 50 个视频链接")

    batch_id = f"batch-{uuid.uuid4().hex[:8]}"
    event_queue = asyncio.Queue()
    tasks[batch_id] = {
        "status": "queued",
        "events": event_queue,
        "kind": "batch",
    }
    background_tasks.add_task(run_batch_pipeline, batch_id, urls, event_queue)
    return AnalyzeResponse(task_id=batch_id, status="queued")


@router.get("/api/analyze/{task_id}/stream")
async def stream_progress(task_id: str):
    if task_id not in tasks:
        raise HTTPException(404, "Task not found")

    async def event_generator():
        queue = tasks[task_id]["events"]
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=300)
                yield {
                    "event": event["type"],
                    "data": json.dumps(event["data"], ensure_ascii=False),
                }
                if event["type"] in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}

    return EventSourceResponse(event_generator())
