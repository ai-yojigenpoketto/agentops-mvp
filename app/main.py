from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.logging import setup_logging
from app.core.db import init_db
from app.core.settings import settings
from app.api import agent_runs, rca_runs, stream, metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management."""
    # Startup
    setup_logging()
    init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="AgentOps Smart SRE",
    description="Production-lean AgentOps MVP with RCA capabilities",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware - MUST be added before routers
# This is required for:
# 1. Browser fetch() calls from Next.js UI (localhost:3000)
# 2. SSE streaming (EventSource requires CORS for cross-origin)
# 3. Preflight OPTIONS requests
cors_origins = settings.get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Required for SSE to work properly
)

# Include routers
app.include_router(agent_runs.router)
app.include_router(rca_runs.router)
app.include_router(stream.router)
app.include_router(metrics.router)


@app.get("/")
def root():
    """Health check."""
    return {"status": "ok", "service": "agentops-smart-sre"}
