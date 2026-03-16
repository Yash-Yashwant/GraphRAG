#!/bin/bash
# Deploy GROBID on a GCE VM - always warm, no cold starts
# Prerequisites: gcloud CLI, authenticated, project set
set -e

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project)}"
ZONE="${GCP_ZONE:-us-central1-a}"
VM_NAME="grobid-vm"
MACHINE_TYPE="e2-standard-4"  # 4 vCPU, 16GB RAM. Use e2-standard-2 (2 vCPU, 8GB) for ~$50/mo

echo "Deploying GROBID on GCE VM..."
echo "  Project: $PROJECT_ID"
echo "  Zone:    $ZONE"
echo "  VM:      $VM_NAME"
echo "  Type:    $MACHINE_TYPE"
echo ""

# Enable Compute Engine API if needed
gcloud services enable compute.googleapis.com --project="$PROJECT_ID"

# Create firewall rule for GROBID port (if not exists)
FIREWALL_NAME="allow-grobid"
if ! gcloud compute firewall-rules describe "$FIREWALL_NAME" --project="$PROJECT_ID" &>/dev/null; then
  echo "Creating firewall rule..."
  gcloud compute firewall-rules create "$FIREWALL_NAME" \
    --project="$PROJECT_ID" \
    --allow=tcp:8070 \
    --source-ranges=0.0.0.0/0 \
    --description="Allow GROBID API"
fi

# Write startup script to temp file
STARTUP_FILE=$(mktemp)
cat > "$STARTUP_FILE" << 'SCRIPT'
#!/bin/bash
set -e
apt-get update -qq && apt-get install -y -qq docker.io
systemctl start docker
docker pull lfoppiano/grobid:0.8.0
docker run -d --name grobid --restart=unless-stopped -p 8070:8070 lfoppiano/grobid:0.8.0
SCRIPT

# Create or recreate VM
if gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" 2>/dev/null; then
  echo "VM exists. Deleting..."
  gcloud compute instances delete "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --quiet
fi

echo "Creating VM..."
gcloud compute instances create "$VM_NAME" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=50GB \
  --metadata-from-file=startup-script="$STARTUP_FILE"

rm -f "$STARTUP_FILE"

echo ""
echo "Waiting for VM to start (60s)..."
sleep 60

# Get external IP
EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "GROBID VM is starting. GROBID takes ~60-90s after VM boots."
echo "  (Docker install ~30s + GROBID Java startup ~60s)"
echo ""
echo "  VM IP:      $EXTERNAL_IP"
echo "  GROBID URL: http://$EXTERNAL_IP:8070"
echo ""
echo "Update config.json:"
echo "  \"grobid_server\": \"http://$EXTERNAL_IP:8070\""
echo ""
echo "Check status (wait ~2 min): curl http://$EXTERNAL_IP:8070/api/isalive"
echo ""
echo "Cost: e2-standard-4 ~\$100/mo. Use e2-medium (2 vCPU, 4GB) for ~\$25/mo if needed."
echo ""
