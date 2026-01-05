# Research Intelligence Engine: System Design & Roadmap

## 1. High-Level Architecture

The goal is to move from a basic PDF parser to a **Resilient ETL Pipeline** that builds a **Self-Resolving Knowledge Graph**.

### The 4-Layer Stack

1. **Ingestion Layer (FastAPI + BackgroundTasks):** Handles the "dump" of 50+ papers. Manages memory via semaphores and tracks job state.
2. **Extraction Layer (GROBID + Marker):** Dual-stream processing for structured XML (entities) and clean Markdown (text).
3. **Knowledge Layer (Neo4j + Pinecone):** The "Dual-Store." Neo4j handles relationships (Citations, Authors); Pinecone handles semantic search (Chunks).
4. **Intelligence Layer (GraphRAG + Gemini):** Hybrid retrieval that traverses the graph to provide expert-level context to the LLM.

---

## 2. The Execution Roadmap (28-Day "Elite" Sprint)

### Phase 1: Resilient Ingestion (Days 1–7)

* **Persistent Job Tracking:** Implement `:Job` nodes in Neo4j to track status (`QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`).
* **The Global Semaphore:** Limit concurrency to 1–2 papers to protect Hugging Face RAM.
* **Atomic Cleanup:** Ensure temporary files are deleted only after successful DB writes.

### Phase 2: Structured Knowledge Extraction (Days 8–14)

* **Entity Resolution:** Python logic to clean GROBID XML. Implement "Fuzzy Matching" to merge authors like "J. Doe" and "John Doe."
* **Citation Mapping:** Automatically create `(Paper)-[:CITES]->(Paper)` relationships.
* **Section-Aware Chunking:** Use Marker’s Markdown to split text by headers (e.g., `## Methodology`) rather than arbitrary character counts.

### Phase 3: Hybrid Retrieval Engine (Days 15–21)

* **GraphRAG Implementation:** Develop a search function that:
1. Finds relevant chunks in Pinecone.
2. Finds neighboring nodes (co-authors, cited works) in Neo4j.
3. Combines them for the LLM prompt.


* **Expert Filters:** Ability to filter search by "Papers published after 2023" or "Papers citing [Author Name]."

### Phase 4: Observability & UI (Days 22–28)

* **Reasoning Traces:** Visualize the "Path" the agent took through the graph.
* **Batch Dashboard:** A Streamlit or FastAPI UI to monitor the 50-paper ingestion progress.

---

## 3. Database Schema Contract

### Neo4j Nodes & Edges

* **(:Paper {id, title, year, abstract, markdown})**
* **(:Author {name, affiliation})**
* **(:Task {name})** (e.g., "Path Planning," "LLM Reasoning")
* **[:AUTHORED_BY]**, **[:CITES]**, **[:UTILIZES_TASK]**

### Pinecone Metadata

* `paper_id`: Links the vector chunk back to the Neo4j node.
* `section`: (Abstract, Introduction, etc.)
* `content`: The raw text chunk.

---

## 4. "Bulletproof" Verification Checklist

* [ ] **Idempotency:** Re-uploading the same 50 papers does not create duplicate nodes.
* [ ] **Resilience:** If the container crashes, I can see which jobs were "IN_PROGRESS" and resume them.
* [ ] **Accuracy:** Author "John Doe" from Paper A and Paper B is the same node in Neo4j.
* [ ] **Performance:** Hybrid search returns results in under 3 seconds.
