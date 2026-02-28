# Deploying GROBID and Marker to Cloud Run

This guide covers deploying the GROBID and Marker PDF services to Google Cloud Run so the main GraphRAG app can use them.

## Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`) installed and authenticated
- A GCP project with billing enabled
- APIs enabled: Cloud Run, Cloud Build, Artifact Registry (or Container Registry)

```bash
# Enable required APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com
```

## 1. Deploy GROBID

GROBID extracts structured metadata (title, authors, citations) from PDFs. We use the **lightweight** `lfoppiano/grobid` image (~300MB) because the full `grobid/grobid` image (~10GB) exceeds Cloud Run's 9.9GB layer limit.

```bash
cd deploy
chmod +x deploy-grobid.sh
./deploy-grobid.sh
```

Or manually:

```bash
gcloud run deploy grobid-service \
  --image=docker.io/lfoppiano/grobid:0.8.0 \
  --platform=managed \
  --region=us-central1 \
  --port=8070 \
  --memory=2Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=10 \
  --concurrency=1 \
  --timeout=300 \
  --allow-unauthenticated
```

**Get the GROBID URL:**
```bash
gcloud run services describe grobid-service --region=us-central1 --format='value(status.url)'
```

**Update `config.json`** in the project root:
```json
{
  "grobid_server": "https://grobid-service-XXXXX-uc.a.run.app",
  "timeout": 60,
  "coordinates": ["p", "s", "persName", "biblStruct"]
}
```

## 2. Deploy Marker

Marker converts PDFs to Markdown. It uses ML models (surya-ocr, marker-pdf) and needs more memory.

```bash
cd deploy
chmod +x deploy-marker.sh
./deploy-marker.sh
```

Or manually:

```bash
# Build and push (from project root)
gcloud builds submit marker-service \
  --tag=gcr.io/YOUR_PROJECT_ID/marker-service \
  --project=YOUR_PROJECT_ID

# Deploy
gcloud run deploy marker-service \
  --image=gcr.io/YOUR_PROJECT_ID/marker-service \
  --platform=managed \
  --region=us-central1 \
  --port=8080 \
  --memory=4Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=5 \
  --concurrency=1 \
  --timeout=300 \
  --allow-unauthenticated
```

**Get the Marker URL:**
```bash
gcloud run services describe marker-service --region=us-central1 --format='value(status.url)'
```

**Set `MARKER_SERVICE_URL`** when running the main app:
```bash
export MARKER_SERVICE_URL=https://marker-service-XXXXX-uc.a.run.app
```

## 3. Environment Variables

| Variable | Used By | Description |
|----------|---------|-------------|
| `config.json` → `grobid_server` | Main app | GROBID Cloud Run URL |
| `MARKER_SERVICE_URL` | Main app | Marker Cloud Run URL |

## Resource Sizing

| Service | Memory | CPU | Notes |
|---------|--------|-----|-------|
| GROBID | 2Gi | 2 | CRF models; increase if processing large PDFs |
| Marker | 4Gi | 2 | ML models (surya-ocr); cold start ~30–60s |

## Cold Starts

Both services use `min-instances=0` to save cost. First request after idle will be slow:
- **GROBID**: ~15–30 seconds
- **Marker**: ~30–60 seconds (model loading)

For production with low latency needs, set `--min-instances=1` (adds cost).

## Troubleshooting

**GROBID returns 503**
- Check memory; try 4Gi if 2Gi fails
- GROBID uses port 8070; ensure `--port=8070` in deploy

**Marker build fails**
- Ensure `marker-service/` has `Dockerfile`, `app.py`, `requirements.txt`
- Build can take 10+ minutes due to ML dependencies

**CORS / network**
- Cloud Run services allow unauthenticated by default with `--allow-unauthenticated`
- For private access, use VPC Connector or IAM-based auth
