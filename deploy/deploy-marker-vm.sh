#!/bin/bash
# Deploy Marker PDF service on a GCE VM - always warm, no cold starts
# Marker uses OCR (surya-ocr) and needs significant memory for ML models
# Prerequisites: gcloud CLI, authenticated, project set
set -e

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project)}"
ZONE="${GCP_ZONE:-us-central1-a}"
VM_NAME="marker-vm"
MACHINE_TYPE="e2-highmem-4"  # 4 vCPU, 32GB RAM - needed for large arXiv papers (Marker has high memory use)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKER_DIR="$(dirname "$SCRIPT_DIR")/marker-service"
IMAGE_NAME="gcr.io/${PROJECT_ID}/marker-service"

echo "Deploying Marker on GCE VM..."
echo "  Project: $PROJECT_ID"
echo "  Zone:    $ZONE"
echo "  VM:      $VM_NAME"
echo ""

# 1. Build and push Marker image
echo "Building Marker container image..."
gcloud builds submit "$MARKER_DIR" \
  --tag="$IMAGE_NAME" \
  --project="$PROJECT_ID"

# 2. Enable Compute Engine API
gcloud services enable compute.googleapis.com --project="$PROJECT_ID"

# 3. Firewall for port 8080
FIREWALL_NAME="allow-marker"
if ! gcloud compute firewall-rules describe "$FIREWALL_NAME" --project="$PROJECT_ID" &>/dev/null; then
  echo "Creating firewall rule..."
  gcloud compute firewall-rules create "$FIREWALL_NAME" \
    --project="$PROJECT_ID" \
    --allow=tcp:8080 \
    --source-ranges=0.0.0.0/0 \
    --description="Allow Marker API"
fi

# 4. Startup script - run Marker container (uses gcr.io image)
STARTUP_FILE=$(mktemp)
cat > "$STARTUP_FILE" << SCRIPT
#!/bin/bash
set -e
apt-get update -qq && apt-get install -y -qq docker.io curl
systemctl start docker
# Auth to GCR via metadata (VM has cloud-platform scope)
TOKEN=\$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")
if [ -n "\$TOKEN" ]; then
  echo "\$TOKEN" | docker login -u oauth2accesstoken --password-stdin https://gcr.io
fi
docker pull ${IMAGE_NAME}
docker run -d --name marker --restart=unless-stopped -p 8080:8080 ${IMAGE_NAME}
SCRIPT

# 5. Create VM
if gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" 2>/dev/null; then
  echo "VM exists. Deleting..."
  gcloud compute instances delete "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --quiet
fi

echo "Creating VM (Marker needs ~2 min to load ML models)..."
gcloud compute instances create "$VM_NAME" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=50GB \
  --scopes=cloud-platform \
  --metadata-from-file=startup-script="$STARTUP_FILE"

rm -f "$STARTUP_FILE"

echo ""
echo "Waiting for VM to start (90s)..."
sleep 90

EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "Marker VM is starting. ML models take ~2 min to load after first request."
echo ""
echo "  VM IP:       $EXTERNAL_IP"
echo "  Marker URL:  http://$EXTERNAL_IP:8080"
echo ""
echo "Update config.json:"
echo "  \"marker_server\": \"http://$EXTERNAL_IP:8080\""
echo ""
echo "Or set env: MARKER_SERVICE_URL=http://$EXTERNAL_IP:8080"
echo ""
echo "Check health: curl http://$EXTERNAL_IP:8080/health"
echo ""
