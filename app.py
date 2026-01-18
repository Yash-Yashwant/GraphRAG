from fastapi import FastAPI, HTTPException, File, UploadFile
import uuid
from grobid_client.grobid_client import GrobidClient
import shutil
from services.neo4j_service import Neo4jService, get_neo4j_service
import httpx
import os
from bs4 import BeautifulSoup
from contextlib import asynccontextmanager

# Cloud Run service URLs
MARKER_SERVICE_URL = os.getenv("MARKER_SERVICE_URL", "https://marker-service-689943598666.us-central1.run.app")


#life span hanler 

@asynccontextmanager
async def lifespan(app: FastAPI):
    
    try:
        neo4j = get_neo4j_service()
        if neo4j.verify_connection():
            print("connection to Neo4j established")
        else:
            print("failed to connect to Neo4j - Running without graph database")
    except Exception as e:
        print("Error connecting to Neo4j: ", e)

    yield

    # now to close the connection 

    try:
        neo4j = get_neo4j_service()
        neo4j.close()
        print("connection to Neo4j closed")
    except Exception as e:
        pass


# app connection variable for Uvicorn

app = FastAPI(lifespan=lifespan)



@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    """
    Ingest a PDF file: extract entities via GROBID, convert to markdown via Marker,
    and store everything in Neo4j knowledge graph.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    job_id = str(uuid.uuid4())  
    temp_path = os.path.join("/tmp", job_id + ".pdf")

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
            raise Exception(f"GROBID processing failed with status code {status}")

        # Extract structured entities from XML
        entities = extract_entities(xml_out)
        

        # Convert PDF to markdown via Marker Cloud Run service
        with open(temp_path, "rb") as pdf_file:
            async with httpx.AsyncClient(timeout=300.0) as client:
                marker_response = await client.post(
                    f"{MARKER_SERVICE_URL}/convert",
                    files={"file": (file.filename, pdf_file, "application/pdf")}
                )
        
        if marker_response.status_code != 200:
            raise Exception(f"Marker processing failed with status {marker_response.status_code}")
        
        marker_data = marker_response.json()
        full_text = marker_data.get("markdown", "")


         # Store in Neo4j knowledge graph
        graph_result = None
        try:
            neo4j = get_neo4j_service()
            if neo4j.verify_connection():
                graph_result = neo4j.ingest_paper_data(
                    job_id=job_id,
                    title=entities["title"],
                    authors=entities["authors"],
                    citations=entities["citations"],
                    full_text=full_text
                )
        except Exception as neo4j_error:
            print(f"Neo4j storage failed (non-fatal): {neo4j_error}")
            graph_result = {"error": str(neo4j_error)}

        return {
            "job_id": job_id,
            "filename": file.filename,
            "entities": entities,
            "full_text": full_text,
            "graph_storage": graph_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def extract_entities(xml_out):
    """Extract title, authors, and citations from GROBID XML output."""
    soup = BeautifulSoup(xml_out, 'xml')
    
    # Extract title
    title = "Unknown Title"
    title_stmt = soup.find('titleStmt')
    if title_stmt:
        title_elem = title_stmt.find('title')
        if title_elem and title_elem.text:
            title = title_elem.text.strip()
    
    # Extract authors - GROBID puts authors under <author> tags with <persName>
    authors = []
    for author in soup.find_all('author'):
        pers_name = author.find('persName')
        if pers_name:
            first = pers_name.find('forename', type='first')
            last = pers_name.find('surname')
            first_text = first.get_text(strip=True) if first else ''
            last_text = last.get_text(strip=True) if last else ''
            full_name = f"{first_text} {last_text}".strip()
            if full_name:
                authors.append(full_name)
                
    # Extract citations - GROBID uses <biblStruct> for each citation
    citations = []
    for cite in soup.find_all('biblStruct'):
        # Try article title first, then book/other title
        c_title = cite.find('title', level='a') or cite.find('title', level='m')
        if c_title and c_title.text:
            citations.append(c_title.get_text(strip=True))

    return {
        "title": title,
        "authors": authors,
        "citations": citations
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    neo4j_status = "disconnected"
    try:
        neo4j = get_neo4j_service()
        if neo4j.verify_connection():
            neo4j_status = "connected"
    except:
        pass
    
    return {
        "status": "healthy",
        "neo4j": neo4j_status
    }


@app.get("/papers")
async def get_papers(limit: int = 100):
    """Get all ingested papers from the knowledge graph."""
    try:
        neo4j = get_neo4j_service()
        if not neo4j.verify_connection():
            raise HTTPException(status_code=503, detail="Neo4j not connected")
        papers = neo4j.get_all_papers(limit=limit)
        return {"papers": papers, "count": len(papers)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get single paper by title

@app.get("/papers/{title}")
async def get_paper(title: str):
    try:
        neo4j = get_neo4j_service()
        if not neo4j.verify_connection():
            raise HTTPException(status_code=503, detail="Neo4j not connected")
        paper = neo4j.get_paper_by_title(title)
        return paper
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/papers/{title}/related")
async def get_related_papers(title:str):
    """Find papers related to the given paper."""
    try:
        neo4j = get_neo4j_service()
        if not neo4j.verify_connection():
            raise HTTPException(status_code=503, detail="Neo4j not connected")
        related_papers = neo4j.get_related_papers(title)
        return {"related_papers": related_papers}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))