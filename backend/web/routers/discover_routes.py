"""发现搜索路由：提交 YouTube / Instagram 任务 + Dashboard 统计 + SSE 流（纯 JSON API）。"""

import time
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from web.deps import require_auth
from web.task_manager import task_manager
from storage import list_snapshots_db

router = APIRouter(tags=["discover"])


# ── Dashboard 统计 ──

@router.get("/api/dashboard/stats")
async def dashboard_stats(_user=Depends(require_auth)):
    yt_snapshots = list_snapshots_db("youtube")
    ig_snapshots = list_snapshots_db("instagram")
    all_tasks = task_manager.list_tasks()
    running = sum(1 for t in all_tasks if t.status == "running")
    completed_today = sum(
        1 for t in all_tasks
        if t.status == "completed" and (time.time() - t.created_at) < 86400
    )

    task_display = []
    for t in all_tasks[:20]:
        t_dict = t.__dict__.copy()
        elapsed = time.time() - t.created_at
        if elapsed < 60:
            t_dict["created_at_display"] = "刚刚"
        elif elapsed < 3600:
            t_dict["created_at_display"] = f"{int(elapsed // 60)} 分钟前"
        else:
            t_dict["created_at_display"] = f"{int(elapsed // 3600)} 小时前"
        task_display.append(t_dict)

    return {
        "yt_snapshot_count": len(yt_snapshots),
        "ig_snapshot_count": len(ig_snapshots),
        "running_tasks": running,
        "completed_today": completed_today,
        "tasks": task_display,
    }


# ── 关键词列表 ──

@router.get("/api/discover/keywords")
async def discover_keywords(_user=Depends(require_auth)):
    from config import SEARCH_KEYWORDS, SEARCH_KEYWORDS_EXTENDED, SEARCH_KEYWORDS_LONG_TAIL
    return {
        "core": SEARCH_KEYWORDS,
        "extended": SEARCH_KEYWORDS_EXTENDED,
        "long_tail": SEARCH_KEYWORDS_LONG_TAIL,
    }


# ── 提交任务 ──

DEPTH_PRESETS = {
    "fast":     {"strategy": "video",  "pages": 2},
    "standard": {"strategy": "video",  "pages": 3},
    "deep":     {"strategy": "both",   "pages": 3},
}


class YouTubeDiscoverRequest(BaseModel):
    selected_keywords: str = ""
    custom_keywords: str = ""
    min_subscribers: int = 1000
    max_subscribers: int = 200000
    depth: str = "standard"
    max_inactive_days: int = 90


@router.post("/api/discover/youtube")
async def submit_youtube(body: YouTubeDiscoverRequest, user=Depends(require_auth)):
    preset = DEPTH_PRESETS.get(body.depth, DEPTH_PRESETS["standard"])
    params = {
        "selected_keywords": body.selected_keywords,
        "custom_keywords": body.custom_keywords,
        "min_subscribers": body.min_subscribers,
        "max_subscribers": body.max_subscribers,
        "strategy": preset["strategy"],
        "pages": preset["pages"],
        "depth": body.depth,
        "max_inactive_days": body.max_inactive_days,
    }
    task_id = task_manager.submit_youtube(params, user.id)
    return {"task_id": task_id}


class InstagramDiscoverRequest(BaseModel):
    selected_keywords: str = ""
    custom_keywords: str = ""
    min_followers: int = 1000
    max_followers: int = 200000


@router.post("/api/discover/instagram")
async def submit_instagram(body: InstagramDiscoverRequest, user=Depends(require_auth)):
    params = {
        "selected_keywords": body.selected_keywords,
        "custom_keywords": body.custom_keywords,
        "min_followers": body.min_followers,
        "max_followers": body.max_followers,
    }
    task_id = task_manager.submit_instagram(params, user.id)
    return {"task_id": task_id}


# ── 任务状态 ──

@router.get("/api/tasks/{task_id}")
async def task_state(task_id: str, _user=Depends(require_auth)):
    state = task_manager.get_state(task_id)
    if not state:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    return state.__dict__


# ── SSE 流 ──

@router.get("/api/tasks/{task_id}/stream")
async def task_stream(request: Request, task_id: str):
    user_via_header = await require_auth(request)
    return StreamingResponse(
        task_manager.stream_progress(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
