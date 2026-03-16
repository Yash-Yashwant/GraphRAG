"""
Pinecone vector store service for paper chunk embeddings.
Chunks markdown by section headers, embeds with Gemini, upserts to Pinecone.
"""
import os
import re
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

load_dotenv()

# Lazy imports to avoid startup errors if deps missing
_pinecone = None
_genai = None


def _get_pinecone():
    global _pinecone
    if _pinecone is None:
        from pinecone import Pinecone
        _pinecone = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    return _pinecone


def _get_genai():
    global _genai
    if _genai is None:
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
        _genai = genai
    return _genai


def chunk_markdown_by_sections(markdown: str, max_chunk_size: int = 1000) -> List[Dict[str, str]]:
    """
    Split markdown into chunks by ## headers. Each chunk has section name and content.
    Falls back to size-based splitting if no headers found.
    """
    if not markdown or not markdown.strip():
        return []

    chunks = []
    # Split by ## or ### headers (preserve the delimiter for section name)
    sections = re.split(r'\n(#{1,3}\s+.+)', markdown)

    current_section = "Abstract"
    for i, part in enumerate(sections):
        part = part.strip()
        if not part:
            continue
        # Odd-indexed parts are header lines (from the regex capture group)
        if i % 2 == 1 and part.startswith("#"):
            current_section = part.lstrip("#").strip() or current_section
            continue
        # Even-indexed parts are content
        if len(part) <= max_chunk_size:
            chunks.append({"section": current_section, "content": part})
        else:
            # Split long sections by paragraphs or size
            paragraphs = part.split("\n\n")
            buf = []
            buf_len = 0
            for p in paragraphs:
                if buf_len + len(p) > max_chunk_size and buf:
                    chunks.append({"section": current_section, "content": "\n\n".join(buf)})
                    buf, buf_len = [], 0
                buf.append(p)
                buf_len += len(p)
            if buf:
                chunks.append({"section": current_section, "content": "\n\n".join(buf)})

    # Fallback: if no headers found, split by size
    if not chunks and markdown.strip():
        text = markdown.strip()
        for i in range(0, len(text), max_chunk_size):
            chunk_text = text[i : i + max_chunk_size]
            if chunk_text.strip():
                chunks.append({"section": "Body", "content": chunk_text.strip()})

    return chunks


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts using Gemini. Returns list of embedding vectors (768 dims)."""
    genai = _get_genai()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY required for embeddings")

    # models/embedding-001 outputs 3072 dims; truncate to 768 for Pinecone index
    result = genai.embed_content(
        model="models/embedding-001",
        content=texts
    )

    # Single content returns {"embedding": [...]}, batch returns {"embeddings": [[...], ...]}
    if "embedding" in result:
        emb = result["embedding"]
        return [[float(x) for x in emb[:768]]]
    embeddings = result.get("embeddings", [])
    return [[float(x) for x in emb[:768]] for emb in embeddings]


def upsert_paper_chunks(
    job_id: str,
    title: str,
    chunks: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    Embed chunks and upsert to Pinecone. Returns count of vectors upserted.
    """
    api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX", "graphrag-papers")
    if not api_key:
        return {"error": "PINECONE_API_KEY not set", "upserted": 0}

    if not chunks:
        return {"upserted": 0, "message": "No chunks to embed"}

    try:
        pc = _get_pinecone()
        index = pc.Index(index_name)

        # Embed all chunks (batch for efficiency)
        texts = [c["content"] for c in chunks]
        embeddings = embed_texts(texts)

        vectors = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vec_id = f"{job_id}_{i}"
            vectors.append({
                "id": vec_id,
                "values": embedding,
                "metadata": {
                    "paper_id": job_id,
                    "paper_title": title[:1000],  # Pinecone metadata limit
                    "section": chunk["section"][:500],
                    "content": chunk["content"][:40000],  # Pinecone metadata limit
                }
            })

        # Upsert in batches of 100
        batch_size = 100
        upserted = 0
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]
            index.upsert(vectors=batch)
            upserted += len(batch)

        return {"upserted": upserted, "chunks": len(chunks)}
    except Exception as e:
        return {"error": str(e), "upserted": 0}


def search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Semantic search over paper chunks. Returns matching chunks with metadata.
    """
    api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX", "graphrag-papers")
    if not api_key:
        return []

    try:
        # Embed query
        query_embedding = embed_texts([query])[0]

        pc = _get_pinecone()
        index = pc.Index(index_name)

        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True
        )

        matches = []
        for m in results.get("matches", []):
            meta = m.get("metadata") or {}
            matches.append({
                "score": m.get("score"),
                "paper_id": meta.get("paper_id"),
                "paper_title": meta.get("paper_title"),
                "section": meta.get("section"),
                "content": meta.get("content", ""),
            })
        return matches
    except Exception as e:
        print(f"Pinecone search failed: {e}")
        return []
