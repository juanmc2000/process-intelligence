from fastapi import FastAPI

from app.routes.review import router as review_router
from app.routes.runs import router as runs_router
from app.routes.upload import router as upload_router

app = FastAPI(title="Process Intelligence API")

app.include_router(upload_router)
app.include_router(runs_router)
app.include_router(review_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}
