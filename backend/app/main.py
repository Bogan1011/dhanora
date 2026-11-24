from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.db import make_engine
from app.auth import router as auth_router
from app.families import router as family_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = make_engine()
    try:
        yield
    finally:
        app.state.engine.dispose()

app = FastAPI(title="Dhanora", version="0.1.0-alpha", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(family_router)

@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Do not echo raw invalid inputs (passwords or invitation codes).
    return JSONResponse(status_code=422, content={"detail": "Invalid request fields"})

@app.middleware("http")
async def private_api(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

@app.get("/health")
def health():
    return {"status": "ok", "service": "dhanora"}

@app.get("/ready")
def ready(request: Request):
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
        if revision != "0003_family":
            return JSONResponse(status_code=503, content={"status": "unavailable"})
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ready", "database": "connected", "schema": revision}

@app.get("/api/v1/status")
def status():
    return {"application": "Dhanora", "version": "0.1.0-alpha", "mode": "development", "ai": "disabled"}
