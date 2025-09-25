# 🚀 OpenShift Resource Governance - Guia de Deploy

## 📋 Visão Geral

Esta aplicação monitora e analisa recursos (CPU/Memory) de pods em clusters OpenShift, fornecendo validações e recomendações baseadas em melhores práticas.

## 🔧 Pré-requisitos

- **OpenShift CLI (oc)** instalado e configurado
- **Acesso a um cluster OpenShift** (público ou privado)
- **Permissões de cluster-admin** ou admin do namespace

## 🚀 Deploy Rápido

### 1. Clone o repositório
```bash
git clone https://github.com/andersonid/openshift-resource-governance.git
cd openshift-resource-governance
```

### 2. Faça login no OpenShift
```bash
oc login https://your-cluster.com
# Ou para clusters internos:
oc login https://api.internal-cluster.com --token=your-token
```

### 3. Deploy da aplicação
```bash
# Deploy simples
./deploy-to-cluster.sh

# Deploy com imagem específica
./deploy-to-cluster.sh andersonid/resource-governance:v1.0.0

# Deploy zero-downtime (recomendado para produção)
./deploy-zero-downtime.sh
```

## 🌐 Acesso à Aplicação

### Via OpenShift Route (recomendado)
```bash
# Obter URL da rota
oc get route resource-governance-route -n resource-governance

# Acessar no navegador
# https://resource-governance-route-your-cluster.com
```

### Via Port-Forward (desenvolvimento)
```bash
# Iniciar port-forward
oc port-forward service/resource-governance-service 8080:8080 -n resource-governance

# Acessar no navegador
# http://localhost:8080
```

## 🔄 Atualizações

### Atualização Automática (GitHub Actions)
- Push para branch `main` → Build automático da imagem
- Imagem disponível em: `andersonid/resource-governance:latest`

### Atualização Manual
```bash
# 1. Fazer pull da nova imagem
oc set image deployment/resource-governance resource-governance=andersonid/resource-governance:latest -n resource-governance

# 2. Aguardar rollout
oc rollout status deployment/resource-governance -n resource-governance

# 3. Verificar status
oc get pods -n resource-governance
```

## 🛠️ Configuração Avançada

### ConfigMap
```bash
# Editar configurações
oc edit configmap resource-governance-config -n resource-governance

# Aplicar mudanças
oc rollout restart deployment/resource-governance -n resource-governance
```

### Recursos e Limites
```bash
# Verificar recursos atuais
oc describe deployment resource-governance -n resource-governance

# Ajustar recursos (se necessário)
oc patch deployment resource-governance -n resource-governance -p '{"spec":{"template":{"spec":{"containers":[{"name":"resource-governance","resources":{"requests":{"cpu":"100m","memory":"256Mi"},"limits":{"cpu":"500m","memory":"1Gi"}}}]}}}}'
```

## 🔍 Troubleshooting

### Verificar Status
```bash
# Status geral
oc get all -n resource-governance

# Logs da aplicação
oc logs -f deployment/resource-governance -n resource-governance

# Eventos do namespace
oc get events -n resource-governance --sort-by='.lastTimestamp'
```

### Problemas Comuns

#### 1. Pod não inicia
```bash
# Verificar logs
oc logs deployment/resource-governance -n resource-governance

# Verificar eventos
oc describe pod -l app.kubernetes.io/name=resource-governance -n resource-governance
```

#### 2. Erro de permissão
```bash
# Verificar RBAC
oc get clusterrole resource-governance-role
oc get clusterrolebinding resource-governance-binding

# Recriar RBAC se necessário
oc apply -f k8s/rbac.yaml
```

#### 3. Imagem não encontrada
```bash
# Verificar se a imagem existe
oc describe deployment resource-governance -n resource-governance

# Forçar pull da imagem
oc set image deployment/resource-governance resource-governance=andersonid/resource-governance:latest -n resource-governance
```

## 📊 Monitoramento

### Health Checks
```bash
# Health check da aplicação
curl http://localhost:8080/api/v1/health

# Status do cluster
curl http://localhost:8080/api/v1/status
```

### Métricas
- **Total de Pods**: Número total de pods analisados
- **Namespaces**: Número de namespaces monitorados
- **Problemas Críticos**: Validações com severidade crítica
- **Análise Histórica**: Dados do Prometheus (se disponível)

## 🔐 Segurança

### RBAC
A aplicação usa um ServiceAccount com permissões mínimas necessárias:
- `get`, `list` pods em todos os namespaces
- `get`, `list` nodes
- `get`, `list` VPA resources

### Network Policies
Para clusters com Network Policies ativas, adicione:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: resource-governance-netpol
  namespace: resource-governance
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: resource-governance
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from: []
  egress:
  - to: []
```

## 📝 Logs e Debugging

### Logs da Aplicação
```bash
# Logs em tempo real
oc logs -f deployment/resource-governance -n resource-governance

# Logs com timestamp
oc logs deployment/resource-governance -n resource-governance --timestamps=true
```

### Debug de Conectividade
```bash
# Testar conectividade com API do Kubernetes
oc exec deployment/resource-governance -n resource-governance -- curl -k https://kubernetes.default.svc.cluster.local/api/v1/pods

# Testar conectividade com Prometheus (se configurado)
oc exec deployment/resource-governance -n resource-governance -- curl http://prometheus.openshift-monitoring.svc.cluster.local:9090/api/v1/query
```

## 🆘 Suporte

### Informações do Cluster
```bash
# Versão do OpenShift
oc version

# Informações do cluster
oc cluster-info

# Recursos disponíveis
oc get nodes
oc top nodes
```

### Coletar Informações para Debug
```bash
# Script de diagnóstico
oc get all -n resource-governance -o yaml > resource-governance-debug.yaml
oc describe deployment resource-governance -n resource-governance >> resource-governance-debug.yaml
oc logs deployment/resource-governance -n resource-governance >> resource-governance-debug.yaml
```

---

## 🎯 Próximos Passos

1. **Configure alertas** para problemas críticos
2. **Integre com Prometheus** para análise histórica
3. **Configure VPA** para namespaces críticos
4. **Personalize validações** conforme suas políticas

---

**Desenvolvido por:** Anderson Nobre  
**Repositório:** https://github.com/andersonid/openshift-resource-governance  
**Suporte:** Abra uma issue no GitHub
