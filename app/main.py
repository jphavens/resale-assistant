"""FastAPI app entrypoint.

M2 (intake, review UI, queue) is not built yet — this is a scaffold with a
health check so Docker Compose has something to run.
"""
from fastapi import FastAPI

app = FastAPI(title="Resale Listing Assistant")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
