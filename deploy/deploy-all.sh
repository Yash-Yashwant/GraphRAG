#!/bin/bash
# Deploy both GROBID and Marker services to Cloud Run
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Step 1: Deploy GROBID ==="
./deploy-grobid.sh

echo ""
echo "=== Step 2: Deploy Marker ==="
./deploy-marker.sh

echo ""
echo "=== Deployment complete ==="
echo ""
echo "Next steps:"
echo "1. Get GROBID URL: gcloud run services describe grobid-service --region=us-central1 --format='value(status.url)'"
echo "2. Update config.json with the GROBID URL"
echo "3. Get Marker URL: gcloud run services describe marker-service --region=us-central1 --format='value(status.url)'"
echo "4. Set MARKER_SERVICE_URL when running the main app"
