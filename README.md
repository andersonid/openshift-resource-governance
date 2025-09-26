# OpenShift Resource Governance Tool

Uma ferramenta de governança de recursos para clusters OpenShift que vai além do que o Metrics Server e VPA oferecem, fornecendo validações, relatórios e recomendações consolidadas.

## 🚀 Características

- **Coleta Automática**: Coleta requests/limits de todos os pods/containers no cluster
- **Validações Red Hat**: Valida best practices de capacity management
- **Integração VPA**: Consome recomendações do VPA em modo Off
- **Integração Prometheus**: Coleta métricas reais de consumo
- **Relatórios Consolidados**: Gera relatórios em JSON, CSV e PDF
- **UI Web**: Interface simples para visualização e interação
- **Aplicação de Recomendações**: Permite aprovar e aplicar recomendações

## 📋 Requisitos

- OpenShift 4.x
- Prometheus (nativo no OCP)
- VPA (opcional, para recomendações)
- Python 3.11+
- Docker
- OpenShift CLI (oc)

## 🛠️ Instalação

### 🚀 Deploy Rápido (Recomendado)

```bash
# 1. Clone o repositório
git clone <repository-url>
cd RequestsAndLimits

# 2. Faça login no OpenShift
oc login <cluster-url>

# 3. Deploy completo (cria tudo automaticamente)
./scripts/deploy-complete.sh
```

### 📋 Deploy Manual

#### 1. Build da Imagem

```bash
# Build local
./scripts/build.sh

# Build com tag específica
./scripts/build.sh v1.0.0

# Build para registry específico
./scripts/build.sh latest seu-usuario
```

#### 2. Deploy no OpenShift

```bash
# Aplicar todos os recursos
oc apply -f k8s/

# Aguardar deployment
oc rollout status deployment/resource-governance -n resource-governance
```

#### 🚀 CI/CD Automático (Recomendado para Produção)
```bash
# 1. Configurar secrets do GitHub
./scripts/setup-github-secrets.sh

# 2. Fazer commit e push
git add .
git commit -m "Nova funcionalidade"
git push origin main

# 3. GitHub Actions fará deploy automático!
```

**Fluxo Automático:**
- ✅ **Push para main** → GitHub Actions detecta mudança
- ✅ **Build automático** → Nova imagem no Docker Hub
- ✅ **Deploy automático** → OpenShift atualiza deployment
- ✅ **Rolling Update** → Zero downtime
- ✅ **Health Checks** → Validação automática

#### 🔧 Deploy Manual (Desenvolvimento)
```bash
# Deploy com estratégia Blue-Green
./scripts/blue-green-deploy.sh

# Deploy com tag específica
./scripts/blue-green-deploy.sh v1.2.0

# Testar fluxo CI/CD localmente
./scripts/test-ci-cd.sh
```

**Scripts para Desenvolvimento:**
- ✅ **Controle total** sobre o processo
- ✅ **Iteração rápida** durante desenvolvimento
- ✅ **Debugging** mais fácil
- ✅ **Testes locais** antes de fazer push

#### Deploy Completo (Inicial)
```bash
# Deploy completo com ImagePullSecret (primeira vez)
./scripts/deploy-complete.sh
```

Este script irá:
- ✅ Criar namespace e RBAC
- ✅ Configurar ImagePullSecret para Docker Hub
- ✅ Deploy da aplicação
- ✅ Configurar Service e Route
- ✅ Verificar se tudo está funcionando

#### Deploy Manual
```bash
# Deploy padrão
./scripts/deploy.sh

# Deploy com tag específica
./scripts/deploy.sh v1.0.0

# Deploy para registry específico
./scripts/deploy.sh latest seu-usuario
```

#### Undeploy
```bash
# Remover completamente a aplicação
./scripts/undeploy-complete.sh
```

### 3. Acesso à Aplicação

Após o deploy, acesse a aplicação através da rota criada:

```bash
# Obter URL da rota
oc get route resource-governance-route -n resource-governance

# Acessar via browser
# https://resource-governance-route-resource-governance.apps.openshift.local
```

## 🔧 Configuração

### ConfigMap

A aplicação é configurada através do ConfigMap `resource-governance-config`:

```yaml
data:
  CPU_LIMIT_RATIO: "3.0"                    # Ratio padrão limit:request para CPU
  MEMORY_LIMIT_RATIO: "3.0"                 # Ratio padrão limit:request para memória
  MIN_CPU_REQUEST: "10m"                    # Mínimo de CPU request
  MIN_MEMORY_REQUEST: "32Mi"                # Mínimo de memória request
  CRITICAL_NAMESPACES: |                    # Namespaces críticos para VPA
    openshift-monitoring
    openshift-ingress
    openshift-apiserver
  PROMETHEUS_URL: "http://prometheus.openshift-monitoring.svc.cluster.local:9090"
```

### Variáveis de Ambiente

- `KUBECONFIG`: Caminho para kubeconfig (usado em desenvolvimento)
- `PROMETHEUS_URL`: URL do Prometheus
- `CPU_LIMIT_RATIO`: Ratio CPU limit:request
- `MEMORY_LIMIT_RATIO`: Ratio memória limit:request
- `MIN_CPU_REQUEST`: Mínimo de CPU request
- `MIN_MEMORY_REQUEST`: Mínimo de memória request

## 📊 Uso

### API Endpoints

#### Status do Cluster
```bash
GET /api/v1/cluster/status
```

#### Status de Namespace
```bash
GET /api/v1/namespace/{namespace}/status
```

#### Validações
```bash
GET /api/v1/validations?namespace=default&severity=error
```

#### Recomendações VPA
```bash
GET /api/v1/vpa/recommendations?namespace=default
```

#### Exportar Relatório
```bash
POST /api/v1/export
Content-Type: application/json

{
  "format": "json",
  "namespaces": ["default", "kube-system"],
  "includeVPA": true,
  "includeValidations": true
}
```

### Exemplos de Uso

#### 1. Verificar Status do Cluster
```bash
curl https://resource-governance-route-resource-governance.apps.openshift.local/api/v1/cluster/status
```

#### 2. Exportar Relatório CSV
```bash
curl -X POST https://resource-governance-route-resource-governance.apps.openshift.local/api/v1/export \
  -H "Content-Type: application/json" \
  -d '{"format": "csv", "includeVPA": true}'
```

#### 3. Ver Validações Críticas
```bash
curl "https://resource-governance-route-resource-governance.apps.openshift.local/api/v1/validations?severity=critical"
```

## 🔍 Validações Implementadas

### 1. Requests Obrigatórios
- **Problema**: Pods sem requests definidos
- **Severidade**: Error
- **Recomendação**: Definir requests de CPU e memória

### 2. Limits Recomendados
- **Problema**: Pods sem limits definidos
- **Severidade**: Warning
- **Recomendação**: Definir limits para evitar consumo excessivo

### 3. Ratio Limit:Request
- **Problema**: Ratio muito alto ou baixo
- **Severidade**: Warning/Error
- **Recomendação**: Ajustar para ratio 3:1

### 4. Valores Mínimos
- **Problema**: Requests muito baixos
- **Severidade**: Warning
- **Recomendação**: Aumentar para valores mínimos

### 5. Overcommit
- **Problema**: Requests excedem capacidade do cluster
- **Severidade**: Critical
- **Recomendação**: Reduzir requests ou adicionar nós

## 📈 Relatórios

### Formato JSON
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "total_pods": 150,
  "total_namespaces": 25,
  "total_nodes": 3,
  "validations": [...],
  "vpa_recommendations": [...],
  "summary": {
    "total_validations": 45,
    "critical_issues": 5,
    "warnings": 25,
    "errors": 15
  }
}
```

### Formato CSV
```csv
Pod Name,Namespace,Container Name,Validation Type,Severity,Message,Recommendation
pod-1,default,nginx,missing_requests,error,Container sem requests definidos,Definir requests de CPU e memória
```

## 🔐 Segurança

### RBAC
A aplicação usa um ServiceAccount dedicado com permissões mínimas:

- **Pods**: get, list, watch, patch, update
- **Namespaces**: get, list, watch
- **Nodes**: get, list, watch
- **VPA**: get, list, watch
- **Deployments/ReplicaSets**: get, list, watch, patch, update

### Security Context
- Executa como usuário não-root (UID 1000)
- Usa SecurityContext com runAsNonRoot: true
- Limita recursos com requests/limits

## 🐛 Troubleshooting

### Verificar Logs
```bash
oc logs -f daemonset/resource-governance -n resource-governance
```

### Verificar Status dos Pods
```bash
oc get pods -n resource-governance
oc describe pod <pod-name> -n resource-governance
```

### Verificar RBAC
```bash
oc auth can-i get pods --as=system:serviceaccount:resource-governance:resource-governance-sa
```

### Testar Conectividade
```bash
# Health check
curl https://resource-governance-route-resource-governance.apps.openshift.local/health

# Teste de API
curl https://resource-governance-route-resource-governance.apps.openshift.local/api/v1/cluster/status
```

## 🚀 Desenvolvimento

### Executar Localmente
```bash
# Instalar dependências
pip install -r requirements.txt

# Executar aplicação
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### Executar com Docker
```bash
# Build
docker build -t resource-governance .

# Executar
docker run -p 8080:8080 resource-governance
```

### Testes
```bash
# Testar importação
python -c "import app.main; print('OK')"

# Testar API
curl http://localhost:8080/health
```

## 📝 Roadmap

### Próximas Versões
- [ ] UI Web com gráficos interativos
- [ ] Relatórios PDF com gráficos
- [ ] Regras customizadas por namespace
- [ ] Integração com GitOps (ArgoCD)
- [ ] Notificações via Slack/Teams
- [ ] Métricas customizadas do Prometheus
- [ ] Suporte a múltiplos clusters

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para detalhes.

## 📞 Suporte

Para suporte e dúvidas:
- Abra uma issue no GitHub
- Consulte a documentação do OpenShift
- Verifique os logs da aplicação
# Teste das secrets do GitHub Actions
