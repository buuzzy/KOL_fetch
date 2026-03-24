"""FastAPI 主应用：挂载路由、静态文件、模板。"""

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from web.deps import get_current_user
from web.task_manager import task_manager

WEB_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    task_manager.shutdown()


app = FastAPI(title="KOL 搜索中台", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

from web.routers import auth_routes, discover_routes, snapshot_routes, report_routes, contact_routes

app.include_router(auth_routes.router)
app.include_router(discover_routes.router)
app.include_router(snapshot_routes.router)
app.include_router(report_routes.router)
app.include_router(contact_routes.router)


@app.get("/")
async def index(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return RedirectResponse("/dashboard", status_code=302)
