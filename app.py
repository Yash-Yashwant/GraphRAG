from fastapi import FastAPI, HTTPException, File, UploadFile, BackgroundTasks
import uuid
import json
import logging
import traceback
import asyncio
from grobid_client.grobid_client import GrobidClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import shutil
from services.neo4j_service import Neo4jService, get_neo4j_service
from services.pinecone_service import chunk_markdown_by_sections, upsert_paper_chunks
import httpx
import os
from bs4 import BeautifulSoup
from contextlib import asynccontextmanager

# In-memory job store: job_id -> { status, filename, result, error }
_jobs: dict = {}


def _get_marker_url():
    if os.getenv("MARKER_SERVICE_URL"):
        return os.getenv("MARKER_SERVICE_URL")
    try:
        with open("config.json") as f:
            cfg = json.load(f)
            return cfg.get("marker_server", "")
    except Exception:
        return ""

MARKER_SERVICE_URL = _get_marker_url()


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

    try:
        neo4j = get_neo4j_service()
        neo4j.close()
        print("connection to Neo4j closed")
    except Exception:
        pass


app = FastAPI(lifespan=lifespan)


async def _process_pdf(job_id: str, temp_path: str, filename: str):
    """Background task: GROBID + Marker + Neo4j + Pinecone."""
    _jobs[job_id]["status"] = "processing"
    try:
        # 1. Try GROBID first (fast for text-based arXiv PDFs - ~5-15 sec)
        entities = None
        full_text = ""
        grobid_ok = False
        try:
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
            if status == 200:
                entities = extract_entities(xml_out)
                full_text = extract_full_text_from_tei(xml_out)
                grobid_ok = bool(full_text and len(full_text.strip()) > 100)
                if grobid_ok:
                    logger.info("GROBID extracted full text (%d chars), skipping Marker", len(full_text))
            else:
                grobid_error = (xml_out or "")[:300]
                logger.warning("GROBID failed (status %s): %s", status, grobid_error)
        except Exception as ge:
            logger.warning("GROBID exception (non-fatal): %s", ge)

        # 2. Marker only when GROBID failed or returned no text (scanned/image PDFs)
        if not grobid_ok:
            marker_url = _get_marker_url()
            with open(temp_path, "rb") as pdf_file:
                async with httpx.AsyncClient(timeout=600.0) as http:
                    marker_response = await http.post(
                        f"{marker_url}/convert",
                        files={"file": (filename, pdf_file, "application/pdf")}
                    )

            if marker_response.status_code != 200:
                marker_error = marker_response.text[:500] if marker_response.text else "(no body)"
                logger.error("Marker failed (status %s): %s", marker_response.status_code, marker_error)
                raise Exception(f"Marker failed (status {marker_response.status_code}): {marker_error}")

            full_text = marker_response.json().get("markdown", "")

        # 3. Fallback metadata from markdown if GROBID failed
        if entities is None:
            entities = extract_entities_from_markdown(full_text, filename)

        # 4. Store in Neo4j
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
        except Exception as ne:
            logger.error("Neo4j storage failed (non-fatal): %s", ne)
            graph_result = {"error": str(ne)}

        # 5. Chunk + upsert to Pinecone
        vector_result = None
        try:
            chunks = chunk_markdown_by_sections(full_text)
            vector_result = upsert_paper_chunks(
                job_id=job_id,
                title=entities["title"],
                chunks=chunks
            )
        except Exception as ve:
            logger.error("Pinecone upsert failed (non-fatal): %s", ve)
            vector_result = {"error": str(ve)}

        _jobs[job_id].update({
            "status": "completed",
            "result": {
                "title": entities["title"],
                "authors": entities["authors"],
                "citations_count": len(entities["citations"]),
                "graph_storage": graph_result,
                "vector_storage": vector_result
            }
        })
        logger.info("Job %s completed: %s", job_id, entities["title"])

    except Exception as e:
        logger.error("Job %s failed: %s", job_id, str(e), exc_info=True)
        _jobs[job_id].update({"status": "failed", "error": str(e)})
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/ingest", status_code=202)
async def ingest(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Queue a PDF for ingestion. Returns immediately with a job_id.
    Poll GET /jobs/{job_id} for status.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    job_id = str(uuid.uuid4())
    temp_path = os.path.join("/tmp", job_id + ".pdf")

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    _jobs[job_id] = {"status": "queued", "filename": file.filename}
    background_tasks.add_task(_process_pdf, job_id, temp_path, file.filename)

    return {"job_id": job_id, "status": "queued", "filename": file.filename}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Check the status of an ingestion job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"job_id": job_id, **job}


@app.get("/jobs")
async def list_jobs():
    """List all jobs and their statuses."""
    return {
        "jobs": [{"job_id": jid, **info} for jid, info in _jobs.items()],
        "total": len(_jobs),
        "summary": {
            "queued": sum(1 for j in _jobs.values() if j["status"] == "queued"),
            "processing": sum(1 for j in _jobs.values() if j["status"] == "processing"),
            "completed": sum(1 for j in _jobs.values() if j["status"] == "completed"),
            "failed": sum(1 for j in _jobs.values() if j["status"] == "failed"),
        }
    }


def extract_entities_from_markdown(markdown: str, filename: str) -> dict:
    """Fallback: extract minimal metadata from markdown when GROBID fails."""
    title = "Unknown Title"
    if markdown and markdown.strip():
        lines = markdown.strip().split("\n")
        for line in lines[:20]:
            line = line.strip()
            if line.startswith("# "):
                title = line.lstrip("# ").strip()
                break
            elif len(line) > 10 and not line.startswith("```"):
                title = line[:200]
                break
    if title == "Unknown Title" and filename:
        title = filename.replace(".pdf", "").replace("_", " ").replace("-", " ")
    return {"title": title, "authors": [], "citations": []}


def extract_full_text_from_tei(xml_out: str) -> str:
    """Extract full document body text from GROBID TEI XML."""
    soup = BeautifulSoup(xml_out, 'xml')
    body = soup.find('body')
    if not body:
        return ""
    # Get all paragraph text, preserving section structure via div/head
    parts = []
    for elem in body.find_all(['head', 'p']):
        txt = elem.get_text(separator=' ', strip=True)
        if txt:
            parts.append("## " + txt + "\n" if elem.name == 'head' else txt + "\n")
    return "\n".join(parts).strip() if parts else body.get_text(separator='\n', strip=True)


def extract_entities(xml_out):
    """Extract title, authors, and citations from GROBID XML output."""
    soup = BeautifulSoup(xml_out, 'xml')

    title = "Unknown Title"
    title_stmt = soup.find('titleStmt')
    if title_stmt:
        title_elem = title_stmt.find('title')
        if title_elem and title_elem.text:
            title = title_elem.text.strip()

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

    citations = []
    for cite in soup.find_all('biblStruct'):
        c_title = cite.find('title', level='a') or cite.find('title', level='m')
        if c_title and c_title.text:
            citations.append(c_title.get_text(strip=True))

    return {"title": title, "authors": authors, "citations": citations}


@app.get("/debug/marker")
async def debug_marker():
    """Test Marker connection."""
    marker_url = _get_marker_url().rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{marker_url}/health")
            return {"url": marker_url, "status": r.status_code, "body": r.text}
    except Exception as e:
        return {"url": marker_url, "error": str(e)}


@app.get("/debug/grobid")
async def debug_grobid():
    """Test GROBID connection."""
    grobid_url = None
    try:
        with open("config.json") as f:
            grobid_url = json.load(f).get("grobid_server", "").rstrip("/")
    except Exception:
        pass
    if not grobid_url:
        return {"error": "No grobid_server in config.json"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{grobid_url}/api/isalive")
            return {"url": grobid_url, "status": r.status_code, "body": r.text[:200]}
    except Exception as e:
        return {"url": grobid_url, "error": str(e)}


@app.get("/health")
async def health():
    """Health check endpoint."""
    neo4j_status = "disconnected"
    try:
        neo4j = get_neo4j_service()
        if neo4j.verify_connection():
            neo4j_status = "connected"
    except Exception:
        pass
    return {"status": "healthy", "neo4j": neo4j_status}


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
async def get_related_papers(title: str):
    """Find papers related to the given paper."""
    try:
        neo4j = get_neo4j_service()
        if not neo4j.verify_connection():
            raise HTTPException(status_code=503, detail="Neo4j not connected")
        related_papers = neo4j.find_related_papers(title)
        return {"related_papers": related_papers}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
