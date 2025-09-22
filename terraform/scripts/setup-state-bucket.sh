#!/bin/bash
# Script to set up GCS bucket for Terraform state management

set -e

# Configuration
PROJECT_ID="${1:-}"
BUCKET_NAME="${2:-}"
REGION="${3:-us-central1}"
KMS_KEY_NAME="${4:-}"

if [ -z "$PROJECT_ID" ] || [ -z "$BUCKET_NAME" ]; then
    echo "Usage: $0 <project_id> <bucket_name> [region] [kms_key_name]"
    echo "Example: $0 my-project my-project-terraform-state us-central1"
    exit 1
fi

echo "Setting up Terraform state bucket..."
echo "Project ID: $PROJECT_ID"
echo "Bucket Name: $BUCKET_NAME"
echo "Region: $REGION"

# Enable required APIs
echo "Enabling required Google Cloud APIs..."
gcloud services enable storage.googleapis.com --project="$PROJECT_ID"
gcloud services enable cloudkms.googleapis.com --project="$PROJECT_ID"

# Create KMS key if specified
if [ -n "$KMS_KEY_NAME" ]; then
    echo "Creating KMS key for state encryption..."
    
    # Create keyring if it doesn't exist
    KEYRING_NAME="terraform-state-keyring"
    gcloud kms keyrings create "$KEYRING_NAME" \
        --location="$REGION" \
        --project="$PROJECT_ID" 2>/dev/null || echo "Keyring already exists"
    
    # Create key if it doesn't exist
    gcloud kms keys create "$KMS_KEY_NAME" \
        --keyring="$KEYRING_NAME" \
        --location="$REGION" \
        --purpose=encryption \
        --project="$PROJECT_ID" 2>/dev/null || echo "Key already exists"
    
    KMS_KEY_ID="projects/$PROJECT_ID/locations/$REGION/keyRings/$KEYRING_NAME/cryptoKeys/$KMS_KEY_NAME"
    echo "KMS Key ID: $KMS_KEY_ID"
fi

# Create the bucket
echo "Creating GCS bucket for Terraform state..."
if gsutil ls -b "gs://$BUCKET_NAME" 2>/dev/null; then
    echo "Bucket gs://$BUCKET_NAME already exists"
else
    gsutil mb -p "$PROJECT_ID" -c STANDARD -l "$REGION" "gs://$BUCKET_NAME"
    echo "Created bucket gs://$BUCKET_NAME"
fi

# Enable versioning
echo "Enabling versioning on bucket..."
gsutil versioning set on "gs://$BUCKET_NAME"

# Set lifecycle policy
echo "Setting lifecycle policy..."
cat > /tmp/lifecycle.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {
          "age": 90,
          "isLive": false
        }
      },
      {
        "action": {"type": "Delete"},
        "condition": {
          "numNewerVersions": 10
        }
      }
    ]
  }
}
EOF

gsutil lifecycle set /tmp/lifecycle.json "gs://$BUCKET_NAME"
rm /tmp/lifecycle.json

# Set encryption if KMS key is provided
if [ -n "$KMS_KEY_NAME" ]; then
    echo "Setting default encryption..."
    gsutil kms encryption -k "$KMS_KEY_ID" "gs://$BUCKET_NAME"
fi

# Set bucket permissions (restrict access)
echo "Setting bucket permissions..."
gsutil iam ch allUsers:legacyObjectReader "gs://$BUCKET_NAME" 2>/dev/null || true
gsutil iam ch allAuthenticatedUsers:legacyObjectReader "gs://$BUCKET_NAME" 2>/dev/null || true

# Create service account for Terraform
SA_NAME="terraform-state-manager"
SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"

echo "Creating service account for Terraform..."
gcloud iam service-accounts create "$SA_NAME" \
    --display-name="Terraform State Manager" \
    --description="Service account for managing Terraform state" \
    --project="$PROJECT_ID" 2>/dev/null || echo "Service account already exists"

# Grant necessary permissions
echo "Granting permissions to service account..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/storage.admin"

if [ -n "$KMS_KEY_NAME" ]; then
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/cloudkms.cryptoKeyEncrypterDecrypter"
fi

# Create and download service account key
KEY_FILE="terraform-state-sa-key.json"
echo "Creating service account key..."
gcloud iam service-accounts keys create "$KEY_FILE" \
    --iam-account="$SA_EMAIL" \
    --project="$PROJECT_ID"

echo ""
echo "✅ Terraform state bucket setup complete!"
echo ""
echo "Bucket: gs://$BUCKET_NAME"
echo "Service Account: $SA_EMAIL"
echo "Key File: $KEY_FILE"
echo ""
echo "Next steps:"
echo "1. Store the service account key securely"
echo "2. Set the GOOGLE_APPLICATION_CREDENTIALS environment variable"
echo "3. Update your Terraform backend configuration:"
echo ""
echo "terraform {"
echo "  backend \"gcs\" {"
echo "    bucket = \"$BUCKET_NAME\""
echo "    prefix = \"terraform/state\""
if [ -n "$KMS_KEY_NAME" ]; then
echo "    encryption_key = \"$KMS_KEY_ID\""
fi
echo "  }"
echo "}"
echo ""
echo "4. Initialize Terraform:"
echo "terraform init"