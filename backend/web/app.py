"""FastAPI 主应用：纯 API 服务，CORS 支持。"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.task_manager import task_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    task_manager.shutdown()


app = FastAPI(title="KOL 搜索中台 API")

_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from web.routers import auth_routes, discover_routes, snapshot_routes, report_routes, contact_routes

app.include_router(auth_routes.router)
app.include_router(discover_routes.router)
app.include_router(snapshot_routes.router)
app.include_router(report_routes.router)
app.include_router(contact_routes.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
