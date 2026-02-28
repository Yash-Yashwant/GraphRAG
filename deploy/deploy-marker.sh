#!/bin/bash
# Deploy Marker PDF service to Google Cloud Run
# Prerequisites: gcloud CLI, authenticated, Docker (for build)
set -e

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project)}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="marker-service"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKER_DIR="$(dirname "$SCRIPT_DIR")/marker-service"

echo "Deploying Marker service to Cloud Run..."
echo "  Project: $PROJECT_ID"
echo "  Region:  $REGION"
echo "  Source:  $MARKER_DIR"
echo ""

# Build and push to Artifact Registry (or GCR)
echo "Building container image..."
gcloud builds submit "$MARKER_DIR" \
  --tag="$IMAGE_NAME" \
  --project="$PROJECT_ID"

echo ""
echo "Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image="$IMAGE_NAME" \
  --platform=managed \
  --region="$REGION" \
  --port=8080 \
  --memory=6Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=6 \
  --concurrency=1 \
  --timeout=600 \
  --allow-unauthenticated

echo ""
echo "Marker service deployed. Get the URL with:"
echo "  gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)'"
echo ""
echo "Set MARKER_SERVICE_URL in your main app's environment:"
echo "  export MARKER_SERVICE_URL=\$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')"
