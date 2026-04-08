from fastapi import FastAPI

from app.routers.generate import router as generate_router

app = FastAPI(title="Qimah Tutor API", version="1.0.0")
app.include_router(generate_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
