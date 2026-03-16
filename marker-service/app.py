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
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        temp_path = tmp.name

    try:
        models = get_models()
        text, images, metadata = convert_single_pdf(temp_path, models)
        return {
            "markdown": text or "",
            "metadata": metadata or {}
        }
    except MemoryError as e:
        raise HTTPException(
            status_code=507,
            detail=f"Out of memory. Use VM with more RAM (32GB+). {str(e)}"
        )
    except Exception as e:
        import traceback
        err_detail = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()[:800]}"
        raise HTTPException(status_code=500, detail=err_detail)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@app.get("/health")
async def health():
    return {"status": "ok"}