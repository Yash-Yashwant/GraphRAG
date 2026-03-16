#!/bin/bash
# Reserve static IPs for GROBID and Marker VMs
# Run this once. IPs persist even when VMs are stopped.
# Cost: ~\$3/month per IP when VM is stopped (no charge when VM is running)
set -e

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project)}"
REGION="us-central1"

echo "Reserving static IPs in $REGION..."
echo ""

# Reserve GROBID IP
if gcloud compute addresses describe grobid-ip --region=$REGION --project=$PROJECT_ID &>/dev/null; then
  echo "grobid-ip already exists"
else
  gcloud compute addresses create grobid-ip --region=$REGION --project=$PROJECT_ID
  echo "Created grobid-ip"
fi

# Reserve Marker IP
if gcloud compute addresses describe marker-ip --region=$REGION --project=$PROJECT_ID &>/dev/null; then
  echo "marker-ip already exists"
else
  gcloud compute addresses create marker-ip --region=$REGION --project=$PROJECT_ID
  echo "Created marker-ip"
fi

echo ""
echo "Static IPs:"
gcloud compute addresses describe grobid-ip --region=$REGION --project=$PROJECT_ID --format='value(address)'
gcloud compute addresses describe marker-ip --region=$REGION --project=$PROJECT_ID --format='value(address)'
echo ""
echo "Next: Redeploy VMs with deploy-grobid-vm.sh and deploy-marker-vm.sh"
echo "      (They now use --address=grobid-ip and --address=marker-ip)"
