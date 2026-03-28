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


@router.get("/api/discover/ig-keywords")
async def discover_ig_keywords(_user=Depends(require_auth)):
    from config import IG_SEARCH_KEYWORDS
    return {"keywords": IG_SEARCH_KEYWORDS}


@router.get("/api/discover/llm-options")
async def llm_options(_user=Depends(require_auth)):
    from llm_filter import KOL_TYPE_OPTIONS, EXCLUDE_TYPE_OPTIONS, AUDIENCE_OPTIONS
    return {
        "kol_types": KOL_TYPE_OPTIONS,
        "exclude_types": EXCLUDE_TYPE_OPTIONS,
        "audiences": AUDIENCE_OPTIONS,
    }


# ── 接口预检 ──

@router.get("/api/discover/health-check")
async def health_check(_user=Depends(require_auth)):
    """一键测试 YouTube / TikHub / LLM 接口是否可用。"""
    import requests as http
    results: dict[str, dict] = {}

    from config import YOUTUBE_API_KEYS, TIKHUB_API_KEY, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

    if YOUTUBE_API_KEYS:
        try:
            r = http.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={"part": "snippet", "q": "test", "maxResults": 1, "key": YOUTUBE_API_KEYS[0]},
                timeout=8,
            )
            results["youtube"] = {"ok": r.status_code == 200, "status": r.status_code,
                                  "keys": len(YOUTUBE_API_KEYS)}
        except Exception as e:
            results["youtube"] = {"ok": False, "error": str(e)}
    else:
        results["youtube"] = {"ok": False, "error": "YOUTUBE_API_KEY 未配置"}

    if TIKHUB_API_KEY:
        try:
            r = http.get(
                "https://api.tikhub.io/api/v1/demo/instagram/web/fetch_user_info",
                params={"username": "instagram"},
                headers={"Authorization": f"Bearer {TIKHUB_API_KEY}"},
                timeout=10,
            )
            results["tikhub"] = {"ok": r.status_code == 200, "status": r.status_code}
        except Exception as e:
            results["tikhub"] = {"ok": False, "error": str(e)}
    else:
        results["tikhub"] = {"ok": False, "error": "TIKHUB_API_KEY 未配置"}

    if LLM_API_KEY and LLM_BASE_URL:
        try:
            r = http.get(f"{LLM_BASE_URL}/models", headers={"Authorization": f"Bearer {LLM_API_KEY}"}, timeout=8)
            results["llm"] = {"ok": r.status_code == 200, "status": r.status_code, "model": LLM_MODEL}
        except Exception as e:
            results["llm"] = {"ok": False, "error": str(e)}
    else:
        results["llm"] = {"ok": False, "error": "LLM_API_KEY 或 LLM_BASE_URL 未配置"}

    return results


# ── 提交任务 ──

DEPTH_PRESETS = {
    "fast":     {"strategy": "video",  "pages": 2},
    "standard": {"strategy": "video",  "pages": 3},
    "deep":     {"strategy": "both",   "pages": 3},
}


class LLMCriteria(BaseModel):
    kol_types: list[str] = []
    exclude_types: list[str] = ["media", "institution", "insurance", "realestate"]
    audience: str = "hk_macau"
    custom_requirements: str = ""


class YouTubeDiscoverRequest(BaseModel):
    selected_keywords: str = ""
    custom_keywords: str = ""
    min_subscribers: int = 1000
    max_subscribers: int = 200000
    depth: str = "standard"
    max_inactive_days: int = 90
    llm_criteria: LLMCriteria | None = LLMCriteria()


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
        "llm_criteria": body.llm_criteria.model_dump() if body.llm_criteria else None,
    }
    task_id = task_manager.submit_youtube(params, user.id)
    return {"task_id": task_id}


class InstagramDiscoverRequest(BaseModel):
    selected_keywords: str = ""
    custom_keywords: str = ""
    min_followers: int = 1000
    max_followers: int = 200000
    llm_criteria: LLMCriteria | None = LLMCriteria()


@router.post("/api/discover/instagram")
async def submit_instagram(body: InstagramDiscoverRequest, user=Depends(require_auth)):
    params = {
        "selected_keywords": body.selected_keywords,
        "custom_keywords": body.custom_keywords,
        "min_followers": body.min_followers,
        "max_followers": body.max_followers,
        "llm_criteria": body.llm_criteria.model_dump() if body.llm_criteria else None,
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
