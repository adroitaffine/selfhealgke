#!/bin/bash

# Synthetic Test Runner for Online Boutique
# This script runs Playwright tests continuously for synthetic monitoring
# and integrates with the Auto-Heal Agent

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="configs/online-boutique.config.ts"
DEFAULT_INTERVAL=300 # 5 minutes
DEFAULT_PROJECT="online-boutique-chrome"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] [INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] [SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] [WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR]${NC} $1"
}

# Usage information
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Synthetic Test Runner for Online Boutique Auto-Heal Integration

OPTIONS:
    -c, --continuous        Run tests continuously (default: single run)
    -i, --interval SECONDS  Interval between test runs (default: 300)
    -p, --project PROJECT   Playwright project to run (default: online-boutique-chrome)
    -t, --test PATTERN      Test pattern to run (default: all)
    -u, --url URL          Online Boutique URL (overrides env var)
    -w, --webhook URL       Auto-Heal webhook URL (overrides env var)
    -s, --secret SECRET     Webhook secret (overrides env var)
    -d, --debug            Enable debug mode
    -h, --help             Show this help message

PROJECTS:
    online-boutique-chrome  Standard Chrome tests
    critical-path-chrome    Critical path tests only
    mobile-simulation       Mobile device simulation
    firefox-compatibility  Firefox compatibility tests

EXAMPLES:
    # Single test run
    $0

    # Continuous monitoring every 5 minutes
    $0 --continuous --interval 300

    # Run only critical path tests
    $0 --project critical-path-chrome

    # Run specific test pattern
    $0 --test "**/checkout-flow.spec.ts"

    # Custom configuration
    $0 --url http://online-boutique.example.com --webhook http://auto-heal.example.com/webhook

ENVIRONMENT VARIABLES:
    ONLINE_BOUTIQUE_URL      Base URL for Online Boutique application
    AUTO_HEAL_WEBHOOK_URL    Auto-Heal Agent webhook endpoint
    AUTO_HEAL_WEBHOOK_SECRET Webhook authentication secret
    NODE_ENV                 Environment (development, staging, production)

EOF
}

# Parse command line arguments
parse_args() {
    CONTINUOUS=false
    INTERVAL=$DEFAULT_INTERVAL
    PROJECT=$DEFAULT_PROJECT
    TEST_PATTERN=""
    DEBUG=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -c|--continuous)
                CONTINUOUS=true
                shift
                ;;
            -i|--interval)
                INTERVAL="$2"
                shift 2
                ;;
            -p|--project)
                PROJECT="$2"
                shift 2
                ;;
            -t|--test)
                TEST_PATTERN="$2"
                shift 2
                ;;
            -u|--url)
                export ONLINE_BOUTIQUE_URL="$2"
                shift 2
                ;;
            -w|--webhook)
                export AUTO_HEAL_WEBHOOK_URL="$2"
                shift 2
                ;;
            -s|--secret)
                export AUTO_HEAL_WEBHOOK_SECRET="$2"
                shift 2
                ;;
            -d|--debug)
                DEBUG=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# Validate environment and configuration
validate_environment() {
    log_info "Validating environment..."
    
    # Check if we're in the right directory
    if [[ ! -f "$PROJECT_DIR/package.json" ]]; then
        log_error "Not in Playwright project directory"
        exit 1
    fi
    
    # Check if Playwright is installed
    if ! command -v npx &> /dev/null; then
        log_error "npx not found. Please install Node.js and npm"
        exit 1
    fi
    
    # Check if config file exists
    if [[ ! -f "$PROJECT_DIR/$CONFIG_FILE" ]]; then
        log_error "Config file not found: $CONFIG_FILE"
        exit 1
    fi
    
    # Validate Online Boutique URL
    if [[ -z "${ONLINE_BOUTIQUE_URL:-}" ]]; then
        log_warning "ONLINE_BOUTIQUE_URL not set, using default: http://localhost:8080"
        export ONLINE_BOUTIQUE_URL="http://localhost:8080"
    fi
    
    # Validate webhook URL
    if [[ -z "${AUTO_HEAL_WEBHOOK_URL:-}" ]]; then
        log_warning "AUTO_HEAL_WEBHOOK_URL not set, using default: http://localhost:8080/webhook/failure"
        export AUTO_HEAL_WEBHOOK_URL="http://localhost:8080/webhook/failure"
    fi
    
    # Test Online Boutique connectivity
    log_info "Testing connectivity to Online Boutique: $ONLINE_BOUTIQUE_URL"
    if curl -s --max-time 10 "$ONLINE_BOUTIQUE_URL" > /dev/null; then
        log_success "Online Boutique is accessible"
    else
        log_error "Cannot connect to Online Boutique at $ONLINE_BOUTIQUE_URL"
        exit 1
    fi
    
    log_success "Environment validation completed"
}

# Run Playwright tests
run_tests() {
    local run_id="$(date '+%Y%m%d_%H%M%S')"
    local test_args=()
    
    log_info "Starting test run: $run_id"
    log_info "Project: $PROJECT"
    log_info "Online Boutique URL: $ONLINE_BOUTIQUE_URL"
    log_info "Webhook URL: $AUTO_HEAL_WEBHOOK_URL"
    
    # Build test command
    test_args+=("--config=$CONFIG_FILE")
    test_args+=("--project=$PROJECT")
    
    if [[ -n "$TEST_PATTERN" ]]; then
        test_args+=("$TEST_PATTERN")
    fi
    
    if [[ "$DEBUG" == "true" ]]; then
        test_args+=("--debug")
    fi
    
    # Set environment variables for this test run
    export PLAYWRIGHT_TEST_RUN_ID="$run_id"
    export PLAYWRIGHT_TEST_PROJECT="$PROJECT"
    
    # Run tests
    cd "$PROJECT_DIR"
    
    local exit_code=0
    if npx playwright test "${test_args[@]}"; then
        log_success "Test run $run_id completed successfully"
    else
        exit_code=$?
        log_error "Test run $run_id failed with exit code: $exit_code"
        
        # Generate failure report
        generate_failure_report "$run_id" "$exit_code"
    fi
    
    # Generate test summary
    generate_test_summary "$run_id" "$exit_code"
    
    return $exit_code
}

# Generate failure report
generate_failure_report() {
    local run_id="$1"
    local exit_code="$2"
    
    log_info "Generating failure report for run: $run_id"
    
    local report_file="test-results/failure-report-$run_id.json"
    
    cat > "$report_file" << EOF
{
  "runId": "$run_id",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)",
  "project": "$PROJECT",
  "exitCode": $exit_code,
  "environment": {
    "onlineBoutiqueUrl": "$ONLINE_BOUTIQUE_URL",
    "webhookUrl": "$AUTO_HEAL_WEBHOOK_URL",
    "nodeEnv": "${NODE_ENV:-development}"
  },
  "testResults": "$(find test-results -name "*results*.json" -newer test-results/failure-report-*.json 2>/dev/null | head -1 || echo 'null')"
}
EOF
    
    log_info "Failure report saved: $report_file"
}

# Generate test summary
generate_test_summary() {
    local run_id="$1"
    local exit_code="$2"
    
    local summary_file="test-results/summary-$run_id.txt"
    
    cat > "$summary_file" << EOF
Synthetic Test Run Summary
==========================

Run ID: $run_id
Timestamp: $(date)
Project: $PROJECT
Exit Code: $exit_code
Status: $([ $exit_code -eq 0 ] && echo "PASSED" || echo "FAILED")

Environment:
- Online Boutique URL: $ONLINE_BOUTIQUE_URL
- Webhook URL: $AUTO_HEAL_WEBHOOK_URL
- Node Environment: ${NODE_ENV:-development}

Test Configuration:
- Config File: $CONFIG_FILE
- Test Pattern: ${TEST_PATTERN:-"all tests"}
- Debug Mode: $DEBUG

Results:
$(find test-results -name "*.json" -newer "$summary_file" 2>/dev/null | head -5 | while read -r file; do echo "- $file"; done || echo "- No result files found")

EOF
    
    if [[ $exit_code -eq 0 ]]; then
        log_success "Test summary saved: $summary_file"
    else
        log_error "Test summary saved: $summary_file"
    fi
}

# Continuous monitoring loop
run_continuous() {
    log_info "Starting continuous synthetic monitoring"
    log_info "Interval: ${INTERVAL}s"
    log_info "Project: $PROJECT"
    
    local run_count=0
    local success_count=0
    local failure_count=0
    
    while true; do
        run_count=$((run_count + 1))
        
        log_info "Starting test run #$run_count"
        
        if run_tests; then
            success_count=$((success_count + 1))
            log_success "Run #$run_count completed successfully"
        else
            failure_count=$((failure_count + 1))
            log_error "Run #$run_count failed"
        fi
        
        log_info "Statistics: $run_count total, $success_count success, $failure_count failures"
        
        if [[ "$CONTINUOUS" == "true" ]]; then
            log_info "Waiting ${INTERVAL}s before next run..."
            sleep "$INTERVAL"
        else
            break
        fi
    done
}

# Cleanup function
cleanup() {
    log_info "Cleaning up..."
    
    # Kill any background processes
    jobs -p | xargs -r kill 2>/dev/null || true
    
    # Clean up old test results (keep last 10 runs)
    find test-results -name "summary-*.txt" -type f | sort -r | tail -n +11 | xargs -r rm
    find test-results -name "failure-report-*.json" -type f | sort -r | tail -n +11 | xargs -r rm
    
    log_info "Cleanup completed"
}

# Signal handlers
trap cleanup EXIT
trap 'log_error "Script interrupted"; exit 1' INT TERM

# Main function
main() {
    parse_args "$@"
    validate_environment
    
    if [[ "$CONTINUOUS" == "true" ]]; then
        run_continuous
    else
        run_tests
    fi
}

# Run main function
main "$@"