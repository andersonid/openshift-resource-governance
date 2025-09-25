# Makefile para OpenShift Resource Governance Tool

# Configurações
IMAGE_NAME = resource-governance
TAG = latest
REGISTRY = andersonid
FULL_IMAGE_NAME = $(REGISTRY)/$(IMAGE_NAME):$(TAG)
NAMESPACE = resource-governance

# Cores para output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[1;33m
BLUE = \033[0;34m
NC = \033[0m # No Color

.PHONY: help build test deploy undeploy clean dev logs status

help: ## Mostrar ajuda
	@echo "$(BLUE)OpenShift Resource Governance Tool$(NC)"
	@echo ""
	@echo "Comandos disponíveis:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

build: ## Build da imagem Docker
	@echo "$(YELLOW)📦 Building Docker image...$(NC)"
	@./scripts/build.sh $(TAG) $(REGISTRY)

test: ## Testar a aplicação
	@echo "$(YELLOW)🧪 Testing application...$(NC)"
	@python -c "import app.main; print('$(GREEN)✅ App imports successfully$(NC)')"
	@echo "$(YELLOW)🧪 Testing API...$(NC)"
	@python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 &
	@sleep 5
	@curl -f http://localhost:8080/health || (echo "$(RED)❌ Health check failed$(NC)" && exit 1)
	@pkill -f uvicorn
	@echo "$(GREEN)✅ Tests passed$(NC)"

deploy: ## Deploy no OpenShift
	@echo "$(YELLOW)🚀 Deploying to OpenShift...$(NC)"
	@./scripts/deploy.sh $(TAG) $(REGISTRY)

undeploy: ## Remover do OpenShift
	@echo "$(YELLOW)🗑️  Undeploying from OpenShift...$(NC)"
	@./scripts/undeploy.sh

clean: ## Limpar recursos locais
	@echo "$(YELLOW)🧹 Cleaning up...$(NC)"
	@docker rmi $(FULL_IMAGE_NAME) 2>/dev/null || true
	@docker system prune -f
	@echo "$(GREEN)✅ Cleanup completed$(NC)"

dev: ## Executar em modo desenvolvimento
	@echo "$(YELLOW)🔧 Starting development server...$(NC)"
	@python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

logs: ## Ver logs da aplicação
	@echo "$(YELLOW)📋 Showing application logs...$(NC)"
	@oc logs -f daemonset/$(IMAGE_NAME) -n $(NAMESPACE)

status: ## Ver status da aplicação
	@echo "$(YELLOW)📊 Application status:$(NC)"
	@oc get all -n $(NAMESPACE)
	@echo ""
	@echo "$(YELLOW)🌐 Route URL:$(NC)"
	@oc get route $(IMAGE_NAME)-route -n $(NAMESPACE) -o jsonpath='{.spec.host}' 2>/dev/null || echo "Route not found"

install-deps: ## Instalar dependências Python
	@echo "$(YELLOW)📦 Installing Python dependencies...$(NC)"
	@pip install -r requirements.txt
	@echo "$(GREEN)✅ Dependencies installed$(NC)"

format: ## Formatar código Python
	@echo "$(YELLOW)🎨 Formatting Python code...$(NC)"
	@python -m black app/
	@python -m isort app/
	@echo "$(GREEN)✅ Code formatted$(NC)"

lint: ## Verificar código Python
	@echo "$(YELLOW)🔍 Linting Python code...$(NC)"
	@python -m flake8 app/
	@python -m mypy app/
	@echo "$(GREEN)✅ Linting completed$(NC)"

security: ## Verificar segurança
	@echo "$(YELLOW)🔒 Security check...$(NC)"
	@python -m bandit -r app/
	@echo "$(GREEN)✅ Security check completed$(NC)"

all: clean install-deps format lint test build ## Executar pipeline completo

# Comandos específicos do OpenShift
oc-login: ## Fazer login no OpenShift
	@echo "$(YELLOW)🔐 Logging into OpenShift...$(NC)"
	@oc login

oc-projects: ## Listar projetos OpenShift
	@echo "$(YELLOW)📋 OpenShift projects:$(NC)"
	@oc get projects

oc-ns: ## Criar namespace
	@echo "$(YELLOW)📁 Creating namespace...$(NC)"
	@oc apply -f k8s/namespace.yaml

oc-rbac: ## Aplicar RBAC
	@echo "$(YELLOW)🔐 Applying RBAC...$(NC)"
	@oc apply -f k8s/rbac.yaml

oc-config: ## Aplicar ConfigMap
	@echo "$(YELLOW)⚙️  Applying ConfigMap...$(NC)"
	@oc apply -f k8s/configmap.yaml

oc-deploy: ## Aplicar DaemonSet
	@echo "$(YELLOW)📦 Applying DaemonSet...$(NC)"
	@oc apply -f k8s/daemonset.yaml

oc-service: ## Aplicar Service
	@echo "$(YELLOW)🌐 Applying Service...$(NC)"
	@oc apply -f k8s/service.yaml

oc-route: ## Aplicar Route
	@echo "$(YELLOW)🛣️  Applying Route...$(NC)"
	@oc apply -f k8s/route.yaml

oc-apply: oc-ns oc-rbac oc-config oc-deploy oc-service oc-route ## Aplicar todos os recursos

# Comandos de monitoramento
monitor: ## Monitorar aplicação
	@echo "$(YELLOW)📊 Monitoring application...$(NC)"
	@watch -n 5 'oc get pods -n $(NAMESPACE) && echo "" && oc get route $(IMAGE_NAME)-route -n $(NAMESPACE)'

health: ## Verificar saúde da aplicação
	@echo "$(YELLOW)🏥 Health check...$(NC)"
	@ROUTE_URL=$$(oc get route $(IMAGE_NAME)-route -n $(NAMESPACE) -o jsonpath='{.spec.host}' 2>/dev/null); \
	if [ -n "$$ROUTE_URL" ]; then \
		curl -f https://$$ROUTE_URL/health || echo "$(RED)❌ Health check failed$(NC)"; \
	else \
		echo "$(RED)❌ Route not found$(NC)"; \
	fi
