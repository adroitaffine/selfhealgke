# Makefile for Terraform operations

.PHONY: help init plan apply destroy validate format lint test clean

# Default environment
ENV ?= development
PROJECT_ID ?= $(shell gcloud config get-value project)
TF_STATE_BUCKET ?= $(PROJECT_ID)-terraform-state

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)GKE Auto-Heal Agent Terraform Operations$(NC)"
	@echo ""
	@echo "$(YELLOW)Usage:$(NC)"
	@echo "  make <target> [ENV=environment] [PROJECT_ID=project]"
	@echo ""
	@echo "$(YELLOW)Targets:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(YELLOW)Examples:$(NC)"
	@echo "  make plan ENV=development"
	@echo "  make apply ENV=production PROJECT_ID=my-project"
	@echo "  make destroy ENV=staging"

setup-state: ## Set up GCS bucket for Terraform state
	@echo "$(BLUE)Setting up Terraform state bucket...$(NC)"
	./scripts/setup-state-bucket.sh $(PROJECT_ID) $(TF_STATE_BUCKET)

init: ## Initialize Terraform
	@echo "$(BLUE)Initializing Terraform for $(ENV) environment...$(NC)"
	terraform init \
		-backend-config="bucket=$(TF_STATE_BUCKET)" \
		-backend-config="prefix=terraform/state/$(ENV)"
	terraform workspace select $(ENV) || terraform workspace new $(ENV)

validate: ## Validate Terraform configuration
	@echo "$(BLUE)Validating Terraform configuration...$(NC)"
	terraform validate
	@echo "$(GREEN)✅ Terraform configuration is valid$(NC)"

format: ## Format Terraform files
	@echo "$(BLUE)Formatting Terraform files...$(NC)"
	terraform fmt -recursive
	@echo "$(GREEN)✅ Terraform files formatted$(NC)"

format-check: ## Check if Terraform files are formatted
	@echo "$(BLUE)Checking Terraform file formatting...$(NC)"
	terraform fmt -check -recursive

lint: ## Run Terraform linting
	@echo "$(BLUE)Running Terraform linting...$(NC)"
	@if command -v tflint >/dev/null 2>&1; then \
		tflint --recursive; \
		echo "$(GREEN)✅ Terraform linting passed$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  tflint not installed, skipping linting$(NC)"; \
	fi

validate-policies: ## Validate Sentinel policies
	@echo "$(BLUE)Validating Sentinel policies...$(NC)"
	./scripts/validate-policies.sh

plan: init validate ## Create Terraform execution plan
	@echo "$(BLUE)Creating Terraform plan for $(ENV) environment...$(NC)"
	terraform plan \
		-var-file="environments/$(ENV)/terraform.tfvars" \
		-var="project_id=$(PROJECT_ID)" \
		-var="terraform_state_bucket=$(TF_STATE_BUCKET)" \
		-out=tfplan-$(ENV)
	@echo "$(GREEN)✅ Terraform plan created: tfplan-$(ENV)$(NC)"

plan-destroy: init ## Create Terraform destroy plan
	@echo "$(BLUE)Creating Terraform destroy plan for $(ENV) environment...$(NC)"
	terraform plan -destroy \
		-var-file="environments/$(ENV)/terraform.tfvars" \
		-var="project_id=$(PROJECT_ID)" \
		-var="terraform_state_bucket=$(TF_STATE_BUCKET)" \
		-out=tfplan-destroy-$(ENV)
	@echo "$(GREEN)✅ Terraform destroy plan created: tfplan-destroy-$(ENV)$(NC)"

apply: ## Apply Terraform changes
	@if [ ! -f "tfplan-$(ENV)" ]; then \
		echo "$(RED)❌ No plan file found. Run 'make plan ENV=$(ENV)' first$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Applying Terraform changes for $(ENV) environment...$(NC)"
	terraform apply tfplan-$(ENV)
	@echo "$(GREEN)✅ Terraform apply completed$(NC)"
	@echo ""
	@echo "$(YELLOW)Cluster connection command:$(NC)"
	@terraform output -raw kubectl_config_command

apply-auto: plan ## Plan and apply Terraform changes automatically
	@echo "$(BLUE)Auto-applying Terraform changes for $(ENV) environment...$(NC)"
	terraform apply -auto-approve \
		-var-file="environments/$(ENV)/terraform.tfvars" \
		-var="project_id=$(PROJECT_ID)" \
		-var="terraform_state_bucket=$(TF_STATE_BUCKET)"
	@echo "$(GREEN)✅ Terraform apply completed$(NC)"

destroy: ## Destroy Terraform-managed infrastructure
	@echo "$(RED)⚠️  WARNING: This will destroy all infrastructure in $(ENV) environment!$(NC)"
	@read -p "Are you sure? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ]
	@echo "$(BLUE)Destroying infrastructure for $(ENV) environment...$(NC)"
	terraform destroy \
		-var-file="environments/$(ENV)/terraform.tfvars" \
		-var="project_id=$(PROJECT_ID)" \
		-var="terraform_state_bucket=$(TF_STATE_BUCKET)"
	@echo "$(GREEN)✅ Infrastructure destroyed$(NC)"

output: ## Show Terraform outputs
	@echo "$(BLUE)Terraform outputs for $(ENV) environment:$(NC)"
	terraform output

state-list: ## List Terraform state resources
	@echo "$(BLUE)Terraform state resources for $(ENV) environment:$(NC)"
	terraform state list

clean: ## Clean up temporary files
	@echo "$(BLUE)Cleaning up temporary files...$(NC)"
	rm -f tfplan-*
	rm -f *.json
	rm -f .terraform.lock.hcl
	@echo "$(GREEN)✅ Cleanup completed$(NC)"

test: validate format-check validate-policies ## Run all tests and validations
	@echo "$(GREEN)✅ All tests passed$(NC)"

# Development shortcuts
dev-plan: ## Quick plan for development environment
	@$(MAKE) plan ENV=development

dev-apply: ## Quick apply for development environment
	@$(MAKE) apply ENV=development

dev-destroy: ## Quick destroy for development environment
	@$(MAKE) destroy ENV=development

# Production safety checks
prod-plan: ## Plan for production (with extra confirmation)
	@echo "$(RED)⚠️  Planning for PRODUCTION environment$(NC)"
	@read -p "Are you sure? Type 'production' to continue: " confirm && [ "$$confirm" = "production" ]
	@$(MAKE) plan ENV=production

prod-apply: ## Apply for production (with extra confirmation)
	@echo "$(RED)⚠️  Applying to PRODUCTION environment$(NC)"
	@read -p "Are you sure? Type 'production' to continue: " confirm && [ "$$confirm" = "production" ]
	@$(MAKE) apply ENV=production