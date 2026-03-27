"""认证路由：登录 / 登出 / 当前用户（纯 JSON API）。"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from web.deps import get_admin_client, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def api_login(body: LoginRequest):
    try:
        client = get_admin_client()
        resp = client.auth.sign_in_with_password({"email": body.email, "password": body.password})
        return {
            "access_token": resp.session.access_token,
            "refresh_token": resp.session.refresh_token,
            "user": {"id": resp.user.id, "email": resp.user.email},
        }
    except Exception as e:
        msg = "邮箱或密码错误"
        if "Email not confirmed" in str(e):
            msg = "邮箱未验证，请检查邮箱"
        return JSONResponse({"error": msg}, status_code=401)


@router.get("/me")
async def api_me(request: Request):
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    return {"id": user.id, "email": user.email}
