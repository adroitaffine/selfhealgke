# Sentinel Configuration File
# Defines policies and their enforcement levels

policy "enforce-private-gke-clusters" {
    source = "./enforce-private-gke-clusters.sentinel"
    enforcement_level = "hard-mandatory"
}

policy "restrict-machine-types" {
    source = "./restrict-machine-types.sentinel"
    enforcement_level = "soft-mandatory"
}

policy "mandatory-security-labels" {
    source = "./mandatory-security-labels.sentinel"
    enforcement_level = "hard-mandatory"
}

# Policy sets for different environments
policy_set "security-policies" {
    policies = [
        "enforce-private-gke-clusters",
        "mandatory-security-labels"
    ]
}

policy_set "cost-control-policies" {
    policies = [
        "restrict-machine-types"
    ]
}

policy_set "all-policies" {
    policies = [
        "enforce-private-gke-clusters",
        "restrict-machine-types", 
        "mandatory-security-labels"
    ]
}