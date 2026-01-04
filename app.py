from fastapi import FastAPI
import uuid
from fastapi import HTTPException
from fastapi import File
from fastapi import UploadFile
from grobid_client.grobid_client import GrobidClient
import shutil
from marker.convert import convert_single_pdf
from marker.models import load_all_models
import os
# This is the "app" variable Uvicorn is looking for
app = FastAPI()
models = load_all_models()

@app.post("/ingest")
async def ingest(file: UploadFile = File(...)): # ... mean that the file is required
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    # now generating a unique job id for the file processing
    job_id = str(uuid.uuid4())
    temp_path = f"temp_{job_id}_{file.filename}"

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    
        client = GrobidClient(config_path="config.json")
        _, status, xml_out = client.process_pdf("processFulltextDocument", temp_path, generateIDs=True)

        if status != 200:
            raise Exception(f"GROBID processing failed with status code{status}")


        # getting the text for marker from teh same temp file at temp_path

        full_text, image, metadata = convert_single_pdf(temp_path, models)

        #returning all the informtion back in teh json form


        return {"job_id": job_id,"filename": file.filename, "metadata_xml":xml_out, "full_text": full_text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    






