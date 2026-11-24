from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.db import make_engine
from app.auth import router as auth_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = make_engine()
    try:
        yield
    finally:
        app.state.engine.dispose()

app = FastAPI(title="Dhanora", version="0.1.0-alpha", lifespan=lifespan)
app.include_router(auth_router)

@app.get("/health")
def health():
    return {"status": "ok", "service": "dhanora"}

@app.get("/ready")
def ready(request: Request):
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
        if revision != "0002_authentication":
            return JSONResponse(status_code=503, content={"status": "unavailable"})
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ready", "database": "connected", "schema": revision}

@app.get("/api/v1/status")
def status():
    return {"application": "Dhanora", "version": "0.1.0-alpha", "mode": "development", "ai": "disabled"}
