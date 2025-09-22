# Infrastructure Deployment Guide

This guide walks you through deploying the GKE Auto-Heal Agent infrastructure using Terraform.

## Prerequisites

### 1. Authentication Setup

First, authenticate with Google Cloud:

```bash
# Login to Google Cloud
gcloud auth login

# Set up Application Default Credentials
gcloud auth application-default login

# Set your project
gcloud config set project cogent-spirit-469200-q3
```

### 2. Validate Prerequisites

Ensure you have the following installed and configured:

- ✅ gcloud CLI installation and authentication
- ✅ Terraform >= 1.5.0 installation
- ✅ kubectl installation
- ✅ Google Cloud project with required APIs enabled
- ✅ Valid Terraform configuration

## Deployment Options

### Option 1: Automated Deployment (Recommended)

Use Terraform directly with make commands:

```bash
# Deploy development environment (default)
cd terraform
make init ENV=development
make plan ENV=development
make apply ENV=development

# Deploy specific environment
make init ENV=staging
make plan ENV=staging
make apply ENV=staging
```

### Option 2: Manual Deployment

If you prefer manual control:

```bash
cd terraform

# 1. Set up Terraform state bucket (manual setup required)
# Create a GCS bucket for Terraform state in your GCP project
# gsutil mb -p your-project-id gs://your-project-id-terraform-state

# 2. Initialize Terraform
terraform init

# 3. Create execution plan
terraform plan -var-file="environments/development/terraform.tfvars"

# 4. Apply infrastructure
terraform apply -var-file="environments/development/terraform.tfvars"
```

## Infrastructure Components

The deployment creates:

### 1. Networking
- **VPC**: Custom network with private subnets
- **Subnets**: 
  - Development: `10.10.0.0/24`
  - Staging: `10.20.0.0/24`
  - Production: `10.30.0.0/24`
- **Cloud NAT**: For outbound internet access
- **Firewall Rules**: Security controls

### 2. GKE Cluster
- **Private Cluster**: No public node IPs
- **Node Pools**: Autoscaling (1-50 nodes based on environment)
- **Machine Types**: 
  - Development: `e2-standard-2` (preemptible)
  - Staging/Production: `e2-standard-4`
- **Security**: Shielded nodes, network policies

### 3. Service Accounts
- **GKE Node SA**: For cluster operations
- **Auto-Heal Agent SA**: For agent operations
- **Terraform SA**: For infrastructure management
- **Monitoring SA**: For observability

### 4. Monitoring
- **Cloud Logging**: Centralized log collection
- **Cloud Monitoring**: Metrics and alerting
- **Dashboards**: Agent health and performance
- **Alert Policies**: SLA monitoring

## Environment Configurations

### Development
- **Purpose**: Development and testing
- **Nodes**: 1-3 preemptible instances
- **Cost**: Optimized for cost savings
- **Access**: More permissive for development

### Staging
- **Purpose**: Pre-production testing
- **Nodes**: 2-10 standard instances
- **Access**: Restricted for security testing

### Production
- **Purpose**: Production workloads
- **Nodes**: 3-50 instances with SSD storage
- **Access**: Most restrictive security
- **Maintenance**: Early morning windows

## Post-Deployment Steps

After successful deployment:

### 1. Configure kubectl
```bash
# Get the connection command from Terraform output
terraform output -raw kubectl_config_command

# Or use the make command
make output ENV=development | grep kubectl_config_command
```

### 2. Verify Cluster Access
```bash
kubectl get nodes
kubectl get namespaces
```

### 3. Deploy Online Boutique
```bash
# Deploy the sample application using kubectl
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/main/release/kubernetes-manifests.yaml -n online-boutique

# Verify deployment
kubectl get pods -n online-boutique
```

### 4. Deploy Auto-Heal Agents
```bash
# Deploy agents and MCP servers
kubectl apply -f kubernetes/agents/
kubectl apply -f kubernetes/mcp-servers/
```

## Monitoring and Verification

### 1. Check Cluster Health
```bash
kubectl get pods --all-namespaces
kubectl top nodes
```

### 2. Verify Monitoring
- Check Cloud Console → Monitoring → Dashboards
- Verify log sinks are working
- Test alert policies

### 3. Security Validation
```bash
# Check network policies
kubectl get networkpolicies

# Verify service accounts
kubectl get serviceaccounts
```

## Troubleshooting

### Common Issues

**1. Authentication Errors**
```bash
# Re-authenticate
gcloud auth login
gcloud auth application-default login
```

**2. API Not Enabled**
```bash
# Enable required APIs
gcloud services enable container.googleapis.com
gcloud services enable compute.googleapis.com
```

**3. Terraform State Lock**
```bash
# Force unlock (use carefully)
terraform force-unlock <lock-id>
```

**4. Resource Quotas**
```bash
# Check quotas
gcloud compute project-info describe --project=cogent-spirit-469200-q3
```

### Debug Commands

```bash
# Enable debug logging
export TF_LOG=DEBUG
export GOOGLE_CREDENTIALS_DEBUG=true

# Check Terraform state
terraform state list
terraform show

# Validate configuration
terraform validate
terraform plan
```

## Cost Optimization

### Development Environment
- Uses preemptible instances (60-91% cost savings)
- Automatic scaling to zero when idle
- Smaller machine types

### Production Environment
- Right-sized instances
- SSD storage for performance
- Committed use discounts available

### Cost Monitoring
```bash
# Set up budget alerts
gcloud billing budgets create \
  --billing-account=<account-id> \
  --display-name="GKE Auto-Heal Budget" \
  --budget-amount=1000USD
```

## Security Considerations

### Network Security
- Private GKE cluster (no public node IPs)
- Master authorized networks
- Network policies enabled
- Cloud NAT for controlled outbound access

### Identity and Access
- Dedicated service accounts with minimal permissions
- Workload Identity for secure pod authentication
- Custom IAM roles following least privilege

### Data Protection
- Encryption at rest for all storage
- TLS encryption for network traffic
- Secrets managed through Kubernetes secrets
- State file encryption with Cloud KMS

## Next Steps

After infrastructure deployment:

1. **Deploy Online Boutique** (Task 9.2)
2. **Configure Monitoring** (Task 9.3)
3. **Validate End-to-End** (Task 10)

## Support

For issues or questions:
- Check the troubleshooting section above
- Review Terraform logs with `TF_LOG=DEBUG`
- Consult the project documentation
- Create an issue in the repository

