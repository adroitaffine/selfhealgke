# GKE Auto-Heal Agent Infrastructure

This directory contains Terraform Infrastructure as Code (IaC) for deploying the GKE Auto-Heal Agent system. The infrastructure includes a VPC-native GKE cluster with private nodes, service accounts with minimal permissions, monitoring, and comprehensive security policies.

## Architecture Overview

The infrastructure is organized into modular components:

- **Networking**: VPC, subnets, Cloud NAT, and firewall rules
- **GKE Cluster**: Private GKE cluster with autoscaling node pools
- **IAM**: Service accounts and custom roles with minimal permissions
- **Monitoring**: Cloud Logging, alerting, and dashboards
- **Security**: Sentinel policies for governance and compliance

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **Terraform** >= 1.5.0
3. **Google Cloud SDK** (gcloud)
4. **Sentinel CLI** (for policy validation)
5. **Required APIs enabled**:
   - Compute Engine API
   - Kubernetes Engine API
   - Cloud Logging API
   - Cloud Monitoring API
   - Cloud Trace API
   - Vertex AI API

## Quick Start

### 1. Set up Terraform State Backend

```bash
# Set your project ID
export PROJECT_ID="your-project-id"

# Create GCS bucket for Terraform state
make setup-state PROJECT_ID=$PROJECT_ID
```

### 2. Configure Environment

```bash
# Copy and customize environment configuration
cp environments/development/terraform.tfvars.example environments/development/terraform.tfvars

# Edit the configuration
vim environments/development/terraform.tfvars
```

### 3. Deploy Infrastructure

```bash
# Development environment
make dev-plan
make dev-apply

# Production environment (with safety checks)
make prod-plan
make prod-apply
```

## Environment Configuration

### Development
- **Purpose**: Development and testing
- **Node Pool**: 1-3 nodes, preemptible instances
- **Machine Type**: e2-standard-2
- **Network**: 10.10.0.0/24 (more permissive access)

### Staging
- **Purpose**: Pre-production testing
- **Node Pool**: 2-10 nodes, standard instances
- **Machine Type**: e2-standard-4
- **Network**: 10.20.0.0/24 (restricted access)

### Production
- **Purpose**: Production workloads
- **Node Pool**: 3-50 nodes, SSD disks
- **Machine Type**: e2-standard-4
- **Network**: 10.30.0.0/24 (most restrictive)

## Terraform Modules

### GKE Cluster Module (`modules/gke-cluster/`)
Creates a VPC-native GKE cluster with:
- Private nodes (no public IPs)
- Workload Identity enabled
- Network policies enabled
- Shielded nodes
- Autoscaling node pools

### Networking Module (`modules/networking/`)
Sets up networking infrastructure:
- VPC with custom subnets
- Secondary ranges for pods and services
- Cloud NAT for outbound internet access
- Firewall rules for security

### IAM Module (`modules/iam/`)
Manages identity and access:
- Custom IAM roles with minimal permissions
- Service accounts for different components
- Workload Identity bindings
- Audit logging configuration

### Monitoring Module (`modules/monitoring/`)
Provides observability:
- Log sinks and storage
- Alert policies for agent health
- Monitoring dashboards
- Notification channels

## Sentinel Policies

Security and compliance policies are enforced using HashiCorp Sentinel:

### Security Policies (Hard Mandatory)
- **Private GKE Clusters**: Ensures all clusters use private nodes
- **Security Labels**: Requires mandatory labels and configurations

### Cost Control Policies (Soft Mandatory)
- **Machine Type Restrictions**: Limits allowed instance types by environment
- **Node Count Limits**: Prevents excessive resource usage
- **Preemptible Nodes**: Requires cost-effective instances for development

### Policy Testing
```bash
# Validate all policies
make validate-policies

# Run policy tests
cd policies && sentinel test

# Apply policies to a plan
sentinel apply -policy-set=all-policies tfplan.json
```

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make help` | Show available commands |
| `make setup-state` | Create GCS bucket for Terraform state |
| `make plan ENV=<env>` | Create execution plan |
| `make apply ENV=<env>` | Apply infrastructure changes |
| `make destroy ENV=<env>` | Destroy infrastructure |
| `make validate` | Validate Terraform configuration |
| `make format` | Format Terraform files |
| `make test` | Run all validations and tests |

## CI/CD Integration

### GitHub Actions Workflows

**Terraform Plan** (`.github/workflows/terraform-plan.yml`)
- Triggered on pull requests
- Runs for all environments
- Validates Terraform and Sentinel policies
- Posts results as PR comments

**Terraform Apply** (`.github/workflows/terraform-apply.yml`)
- Triggered on main branch pushes
- Requires environment approval for production
- Applies changes with policy validation
- Sends notifications to Slack

### Required Secrets

Configure these secrets in your GitHub repository:

```bash
GCP_SA_KEY              # Service account key JSON
GCP_PROJECT_ID          # Google Cloud project ID
TF_STATE_BUCKET         # Terraform state bucket name
SLACK_WEBHOOK_URL       # Slack webhook for notifications
```

## Security Considerations

### Network Security
- Private GKE cluster with no public node IPs
- Master authorized networks restrict API access
- Network policies enabled for pod-to-pod security
- Cloud NAT provides controlled outbound access

### Identity and Access Management
- Dedicated service accounts with minimal permissions
- Workload Identity for secure pod authentication
- Custom IAM roles following principle of least privilege
- Regular audit logging for compliance

### Data Protection
- Encryption at rest for all storage
- TLS encryption for all network traffic
- Secrets managed through Kubernetes secrets
- State file encryption with Cloud KMS

## Monitoring and Alerting

### Key Metrics
- Agent pod health and availability
- Response time SLA (< 90 seconds)
- Error rates and failure patterns
- Resource utilization and costs

### Alert Policies
- Agent pod not running
- High error rate in logs
- Response time SLA violations
- Infrastructure changes

### Dashboards
- Agent health overview
- Performance metrics
- Error log analysis
- Infrastructure status

## Troubleshooting

### Common Issues

**1. Terraform State Lock**
```bash
# Force unlock if needed (use carefully)
terraform force-unlock <lock-id>
```

**2. Policy Violations**
```bash
# Check policy details
sentinel apply -trace -policy-set=all-policies tfplan.json
```

**3. GKE Cluster Access**
```bash
# Configure kubectl
gcloud container clusters get-credentials <cluster-name> --region <region>
```

**4. Service Account Permissions**
```bash
# Check current permissions
gcloud projects get-iam-policy <project-id>
```

### Debugging

Enable detailed logging:
```bash
export TF_LOG=DEBUG
export GOOGLE_CREDENTIALS_DEBUG=true
```

## Cost Optimization

### Development Environment
- Use preemptible nodes (60-91% cost savings)
- Smaller machine types (e2-standard-2)
- Automatic node pool scaling to zero when idle

### Production Environment
- Right-size machine types based on workload
- Use committed use discounts for predictable workloads
- Monitor and alert on cost anomalies

### Cost Monitoring
```bash
# View current costs
gcloud billing budgets list

# Set up budget alerts
gcloud billing budgets create --billing-account=<account-id> \
  --display-name="GKE Auto-Heal Budget" \
  --budget-amount=1000USD
```

## Compliance and Governance

### CIS Benchmark Compliance
- Private clusters (CIS 5.6.1)
- Network policies enabled (CIS 5.6.7)
- Shielded nodes enabled (CIS 5.5.1)
- Audit logging configured (CIS 5.1.1)

### NIST Framework Alignment
- Access Control (AC): IAM and RBAC
- System and Communications Protection (SC): Network security
- Configuration Management (CM): Infrastructure as Code

## Support and Maintenance

### Regular Tasks
- Review and update Terraform modules monthly
- Update provider versions quarterly
- Review and adjust Sentinel policies
- Monitor security advisories

### Backup and Recovery
- Terraform state is versioned in GCS
- Infrastructure can be recreated from code
- Regular backup of cluster configurations
- Disaster recovery procedures documented

## Contributing

1. Create feature branch from `main`
2. Make changes and test locally
3. Run `make test` to validate
4. Create pull request
5. Review Terraform plan in PR comments
6. Merge after approval

For questions or issues, please refer to the project documentation or create an issue in the repository.