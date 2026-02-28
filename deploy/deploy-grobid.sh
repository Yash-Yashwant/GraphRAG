#!/bin/bash
# Deploy GROBID to Google Cloud Run
# Prerequisites: gcloud CLI, authenticated, project set
#
# Verify port locally first:
#   docker run -p 8070:8070 lfoppiano/grobid:0.8.0
#   # Wait ~30-60s for Java to start, then:
#   curl http://localhost:8070/api/isalive
set -e

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project)}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="grobid-service"

echo "Deploying GROBID to Cloud Run..."
echo "  Project: $PROJECT_ID"
echo "  Region:  $REGION"
echo "  Image:   lfoppiano/grobid:0.8.0"
echo ""

gcloud run deploy "$SERVICE_NAME" \
  --image=docker.io/lfoppiano/grobid:0.8.0 \
  --platform=managed \
  --region="$REGION" \
  --port=8070 \
  --memory=4Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=10 \
  --concurrency=1 \
  --timeout=300 \
  --cpu-boost \
  --startup-probe=initialDelaySeconds=90,periodSeconds=15,failureThreshold=20,httpGet.path=/api/isalive,httpGet.port=8070 \
  --allow-unauthenticated

echo ""
echo "GROBID deployed. Get the URL with:"
echo "  gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)'"
echo ""
echo "Update config.json with the service URL:"
echo '  "grobid_server": "<SERVICE_URL>"'
