# AGENTS.md

## Cursor Cloud specific instructions

### Overview

This is a **Research Intelligence Engine** — a FastAPI backend that ingests academic PDFs, extracts metadata via GROBID, converts to Markdown via Marker, and stores entities/relationships in a Neo4j knowledge graph.

### Services

| Service | How to run | Port |
|---------|-----------|------|
| **FastAPI app** | `python3 -m uvicorn app:app --host 0.0.0.0 --port 7860` | 7860 |
| **Neo4j** | Installed via `apt` (`sudo neo4j start`) | 7687 (bolt), 7474 (http) |
| **GROBID** | Remote Cloud Run (configured in `config.json`) | N/A |
| **Marker** | Remote Cloud Run (env `MARKER_SERVICE_URL`) | N/A |

### Neo4j setup

Neo4j is installed system-wide via the official apt repo. Default credentials: `neo4j` / `password`. Start with `sudo neo4j start`, wait ~10s for it to be ready, then run migrations:

```
python3 run_migrations.py
```

### Key gotchas

- The `~/.local/bin` directory must be on `PATH` for `uvicorn` and other pip-installed scripts to be found. This is set in `~/.bashrc`.
- Neo4j requires Java 21 (pre-installed in the VM).
- The `/papers` list endpoint has a known Cypher syntax issue with Neo4j 5.x (aggregation + ORDER BY). The `/papers/{title}` endpoint works correctly.
- The `/papers/{title}/related` endpoint calls `get_related_papers()` but the service method is named `find_related_papers()` — this is a pre-existing code mismatch.
- Remote GROBID and Marker services may be slow or rate-limited. The ingestion endpoint has a 300s timeout for Marker.
- No automated test suite or linting configuration exists in the repo.
