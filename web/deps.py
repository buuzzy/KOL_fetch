"""Supabase 客户端初始化 + FastAPI 认证依赖 + 共享模板。"""

import os
from pathlib import Path

from fastapi import Request, HTTPException
from fastapi.templating import Jinja2Templates
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

WEB_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))

_admin_client: Client | None = None


def get_admin_client() -> Client:
    """Service-role Supabase 客户端，用于后端全部 DB/Auth 操作。"""
    global _admin_client
    if _admin_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 未配置")
        _admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _admin_client


async def get_current_user(request: Request):
    """从 cookie 中取 access_token 并验证，返回 user 或 None。"""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        client = get_admin_client()
        resp = client.auth.get_user(token)
        return resp.user
    except Exception:
        return None


async def require_auth(request: Request):
    """需要认证的 API 路由依赖，未认证则 401。"""
    user = await get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="未登录或 token 已过期")
    return user
