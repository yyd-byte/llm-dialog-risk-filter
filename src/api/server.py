"""FastAPI 服务入口 — 创建应用实例并注册全部路由。

Usage:
    python -m uvicorn src.api.server:app --reload --port 8000
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.bootstrap import AppComponents, bootstrap
from src.api.routes.health import router as health_router
from src.api.routes.pipeline import router as pipeline_router
from src.api.routes.stats import router as stats_router
from src.api.routes.rules import router as rules_router
from src.api.routes.feedback import router as feedback_router
from src.api.routes.audit import router as audit_router

app = FastAPI(
    title="LLM Dialog Risk Filter",
    description="大模型对话内容风控系统 API",
    version="0.1.0",
)

# CORS 中间件：允许前端开发服务器访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)

# 注册路由
app.include_router(health_router)
app.include_router(pipeline_router)
app.include_router(stats_router)
app.include_router(rules_router)
app.include_router(feedback_router)
app.include_router(audit_router)


@app.on_event("startup")
def startup():
    """初始化全部组件。

    加载配置、创建规范化器、检测器、融合器、脱敏器、
    输出复检器、LLM 客户端、审计日志和统计引擎。
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    AppComponents.init(bootstrap(project_root))
    print("API 服务就绪 [OK]")
