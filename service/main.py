from fastapi import FastAPI

from service.webhooks.router import router

app = FastAPI(title="AI Code Reviewer Webhook Service")
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
