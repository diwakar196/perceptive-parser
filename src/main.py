import uvicorn
from fastapi import FastAPI
from src.endpoint.parse import router as parse_router

app = FastAPI()

app.include_router(parse_router)


@app.get("/")
async def root():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

