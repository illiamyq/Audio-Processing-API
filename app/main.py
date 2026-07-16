from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import admin, audio, auth
from app.services.storage import ensure_bucket


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_bucket()
    yield


app = FastAPI(title="Audio Processing API", version="0.1.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(audio.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"status": "ok"}
