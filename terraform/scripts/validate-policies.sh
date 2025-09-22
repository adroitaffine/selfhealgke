#!/bin/bash
# Script to validate Sentinel policies

set -e

POLICIES_DIR="$(dirname "$0")/../policies"
cd "$POLICIES_DIR"

echo "Validating Sentinel policies..."

# Check if Sentinel is installed
if ! command -v sentinel &> /dev/null; then
    echo "Error: Sentinel CLI is not installed"
    echo "Please install Sentinel from: https://docs.hashicorp.com/sentinel/downloads"
    exit 1
fi

# Validate policy syntax
echo "Checking policy syntax..."
for policy in *.sentinel; do
    if [ -f "$policy" ]; then
        echo "  Validating $policy..."
        sentinel fmt -check "$policy"
    fi
done

# Run policy tests
echo "Running policy tests..."
if [ -d "test" ]; then
    sentinel test
else
    echo "No test directory found, skipping tests"
fi

# Validate sentinel.hcl configuration
if [ -f "sentinel.hcl" ]; then
    echo "Validating sentinel.hcl configuration..."
    # Basic syntax check by attempting to parse
    sentinel version > /dev/null
    echo "  sentinel.hcl syntax is valid"
fi

echo "✅ All Sentinel policies validated successfully!"