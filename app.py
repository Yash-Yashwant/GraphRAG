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
from bs4 import BeautifulSoup
# import lxml  
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
        _, status, xml_out = client.process_pdf(
            "processFulltextDocument", 
            temp_path, 
            generateIDs=True, 
            consolidate_header=False, 
            consolidate_citations=False, 
            include_raw_citations=False, 
            include_raw_affiliations=False, 
            tei_coordinates=False, 
            segment_sentences=False
        )
        if status != 200:
            raise Exception(f"GROBID processing failed with status code{status}")


        # Extract structured entities from XML
        entities = extract_entities(xml_out)
        
        # getting the text for marker from teh same temp file at temp_path
        full_text, image, metadata = convert_single_pdf(temp_path, models)

        #returning all the informtion back in teh json form
        return {
            "job_id": job_id,
            "filename": file.filename,
            "entities": entities,      # Structured: title, authors, citations
            "full_text": full_text     # Markdown text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    

def extract_entities(xml_out):
    soup = BeautifulSoup(xml_out, 'xml')
    title = soup.find('titleStmt').find('title').text if soup.find('titleStmt') else "Unknown Title" 
    authors = []
    for author in soup.find_all('author'):
        pers_name = author.find('persName')
        if pers_name:
            first = pers_name.find('forename', type='first')
            last = pers_name.find('surname')
            full_name = f"{first.text if first else ''} {last.text if last else ''}".strip()
            if full_name: authors.append(full_name)

        
    citations = []
    for cite in soup.find_all('biblStruct'):
        c_title = cite.find('title', level='a')
        if c_title: citations.append(c_title.text)


    return {"title": title, "authors": authors, "citations": citations}




    
            
