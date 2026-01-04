from fastapi import FastAPI

# This is the "app" variable Uvicorn is looking for
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "online", "message": "Research Ingestion Engine Ready"}
