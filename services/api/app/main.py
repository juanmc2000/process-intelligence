from fastapi import FastAPI

from app.routes.upload import router as upload_router

app = FastAPI(title="Process Intelligence API")

app.include_router(upload_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}
