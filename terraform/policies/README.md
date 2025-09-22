# Sentinel Policies for GKE Auto-Heal Agent

This directory contains Sentinel policies that enforce security, cost control, and compliance requirements for the GKE Auto-Heal Agent infrastructure.

## Policies

### 1. enforce-private-gke-clusters.sentinel
**Enforcement Level**: Hard Mandatory

Ensures all GKE clusters are configured with:
- Private nodes enabled
- Private endpoint disabled (for external access)
- Master authorized networks configured
- Network policy enabled
- Shielded nodes enabled
- Workload Identity enabled

### 2. restrict-machine-types.sentinel
**Enforcement Level**: Soft Mandatory

Controls costs by enforcing:
- Allowed machine types per environment
- Maximum node counts per environment
- Preemptible nodes for development
- Reasonable disk sizes (≤200GB)
- Required cost/billing labels

### 3. mandatory-security-labels.sentinel
**Enforcement Level**: Hard Mandatory

Requires security and operational labels:
- `environment`: development, staging, production, test
- `managed-by`: terraform
- `purpose`: descriptive purpose
- Logging and monitoring enabled
- Shielded instance configuration
- Descriptive service account names

## Policy Sets

- **security-policies**: Critical security requirements
- **cost-control-policies**: Cost optimization rules
- **all-policies**: Complete policy enforcement

## Testing

Test cases are provided in the `test/` directory:

```bash
# Run policy tests (requires Sentinel CLI)
sentinel test

# Test specific policy
sentinel test enforce-private-gke-clusters

# Apply policies to Terraform plan
sentinel apply -policy-set=all-policies tfplan.json
```

## Environment-Specific Rules

### Development
- Must use preemptible nodes
- Limited to smaller machine types
- Maximum 3 nodes per pool

### Staging
- Moderate machine type restrictions
- Maximum 10 nodes per pool
- Standard security requirements

### Production
- Full range of approved machine types
- Maximum 50 nodes per pool
- Strictest security requirements

## Integration with Terraform

Add to your Terraform Cloud/Enterprise workspace:

```hcl
# terraform.tf
terraform {
  cloud {
    organization = "your-org"
    workspaces {
      name = "gke-auto-heal-agent"
    }
  }
}
```

Configure policy sets in Terraform Cloud:
1. Upload policies to policy sets
2. Attach to workspace
3. Set enforcement levels

## Compliance Mapping

| Policy | Requirement | CIS Benchmark | NIST |
|--------|-------------|---------------|------|
| Private Clusters | 6.2, 6.3 | 5.6.1 | SC-7 |
| Machine Types | 6.4, 6.5 | - | CM-2 |
| Security Labels | 6.4, 6.5 | - | CM-8 |

## Troubleshooting

Common policy violations:

1. **Private cluster not enabled**
   ```
   VIOLATION: google_container_cluster.auto_heal_cluster does not have private nodes enabled
   ```
   Solution: Set `enable_private_nodes = true`

2. **Missing required labels**
   ```
   VIOLATION: google_container_cluster.auto_heal_cluster missing required label: environment
   ```
   Solution: Add required labels to `resource_labels`

3. **Invalid machine type**
   ```
   VIOLATION: google_container_node_pool.auto_heal_node_pool uses disallowed machine type n1-highmem-8 for environment development
   ```
   Solution: Use allowed machine types for the environment