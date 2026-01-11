from fastapi import FastAPI, UploadFile, HTTPException
from fastapi import File
from marker.convert import convert_single_pdf
from marker.models import load_all_models
import tempfile
import os 

app = FastAPI()
# models = load_all_models()

_models = None

def get_models():
    global _models
    if _models is None:
        _models = load_all_models()
    return _models
  


@app.post('/convert')
async def convert(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    #create a temp file and write the uploaded file to it

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        temp_path = tmp.name

    
    try:
        models = get_models()
        text, images, metadata = convert_single_pdf(temp_path, models)
        return {
            "markdown": text,
            "metadata": metadata
        }
    finally:
        os.unlink(temp_path)


@app.get("/health")
async def health():
    return {"status": "ok"}