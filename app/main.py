from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.logging import setup_logging
from app.core.db import init_db
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

# Include routers
app.include_router(agent_runs.router)
app.include_router(rca_runs.router)
app.include_router(stream.router)
app.include_router(metrics.router)


@app.get("/")
def root():
    """Health check."""
    return {"status": "ok", "service": "agentops-smart-sre"}
