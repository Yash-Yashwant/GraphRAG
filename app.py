from fastapi import FastAPI


app = FastAPI()

@app.get("/")
aysnc def root():
	return {"return": "ingestion app is running"}
