# 🚀 Deploy no OpenShift

Este documento explica como fazer deploy da OpenShift Resource Governance Tool no seu cluster OpenShift.

## 📋 Pré-requisitos

- Cluster OpenShift 4.x
- OpenShift CLI (oc) instalado e configurado
- Acesso ao cluster com permissões para criar recursos
- Container Registry (Docker Hub, Quay.io, etc.)

## 🎯 Opções de Deploy

### 1. Deploy Rápido (Recomendado)

```bash
# Clone o repositório
git clone https://github.com/andersonid/openshift-resource-governance.git
cd openshift-resource-governance

# Execute o script de deploy
./openshift-deploy.sh
```

### 2. Deploy via Template OpenShift

```bash
# Processar template com parâmetros
oc process -f openshift-git-deploy.yaml \
  -p GITHUB_REPO="https://github.com/andersonid/openshift-resource-governance.git" \
  -p IMAGE_TAG="latest" \
  -p REGISTRY="andersonid" \
  -p NAMESPACE="resource-governance" | oc apply -f -
```

### 3. Deploy Manual

```bash
# 1. Criar namespace
oc apply -f k8s/namespace.yaml

# 2. Aplicar RBAC
oc apply -f k8s/rbac.yaml

# 3. Aplicar ConfigMap
oc apply -f k8s/configmap.yaml

# 4. Atualizar imagem no DaemonSet
oc set image daemonset/resource-governance resource-governance=andersonid/resource-governance:latest -n resource-governance

# 5. Aplicar recursos
oc apply -f k8s/daemonset.yaml
oc apply -f k8s/service.yaml
oc apply -f k8s/route.yaml
```

## 🔧 Configuração

### Variáveis de Ambiente

A aplicação pode ser configurada através do ConfigMap:

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

### Personalizar Configurações

```bash
# Editar ConfigMap
oc edit configmap resource-governance-config -n resource-governance

# Reiniciar pods para aplicar mudanças
oc rollout restart daemonset/resource-governance -n resource-governance
```

## 🌐 Acesso à Aplicação

### Obter URL da Rota

```bash
# Obter URL da rota
oc get route resource-governance-route -n resource-governance -o jsonpath='{.spec.host}'

# Acessar via browser
# https://resource-governance-route-resource-governance.apps.openshift.local
```

### Testar Aplicação

```bash
# Health check
curl https://resource-governance-route-resource-governance.apps.openshift.local/health

# API status
curl https://resource-governance-route-resource-governance.apps.openshift.local/api/v1/cluster/status
```

## 📊 Monitoramento

### Ver Logs

```bash
# Logs do DaemonSet
oc logs -f daemonset/resource-governance -n resource-governance

# Logs de um pod específico
oc logs -f <pod-name> -n resource-governance
```

### Ver Status

```bash
# Status dos recursos
oc get all -n resource-governance

# Status detalhado do DaemonSet
oc describe daemonset/resource-governance -n resource-governance

# Status dos pods
oc get pods -n resource-governance -o wide
```

### Verificar RBAC

```bash
# Verificar permissões do ServiceAccount
oc auth can-i get pods --as=system:serviceaccount:resource-governance:resource-governance-sa

# Verificar ClusterRole
oc describe clusterrole resource-governance-role
```

## 🔄 Atualizações

### Atualizar Imagem

```bash
# Atualizar para nova tag
oc set image daemonset/resource-governance resource-governance=andersonid/resource-governance:v1.1.0 -n resource-governance

# Aguardar rollout
oc rollout status daemonset/resource-governance -n resource-governance
```

### Atualizar do GitHub

```bash
# Pull das mudanças
git pull origin main

# Deploy com nova tag
./openshift-deploy.sh v1.1.0
```

## 🗑️ Remoção

### Remover Aplicação

```bash
# Usar script de undeploy
./scripts/undeploy.sh

# Ou remover manualmente
oc delete -f k8s/route.yaml
oc delete -f k8s/service.yaml
oc delete -f k8s/daemonset.yaml
oc delete -f k8s/configmap.yaml
oc delete -f k8s/rbac.yaml
oc delete -f k8s/namespace.yaml
```

## 🐛 Troubleshooting

### Problemas Comuns

#### 1. Pod não inicia
```bash
# Verificar eventos
oc get events -n resource-governance --sort-by='.lastTimestamp'

# Verificar logs
oc logs <pod-name> -n resource-governance
```

#### 2. Erro de permissão
```bash
# Verificar RBAC
oc auth can-i get pods --as=system:serviceaccount:resource-governance:resource-governance-sa

# Verificar ServiceAccount
oc get serviceaccount resource-governance-sa -n resource-governance -o yaml
```

#### 3. Erro de conectividade com Prometheus
```bash
# Verificar se Prometheus está acessível
oc exec -it <pod-name> -n resource-governance -- curl http://prometheus.openshift-monitoring.svc.cluster.local:9090/api/v1/query?query=up
```

#### 4. Rota não acessível
```bash
# Verificar rota
oc get route resource-governance-route -n resource-governance -o yaml

# Verificar ingress controller
oc get pods -n openshift-ingress
```

### Logs de Debug

```bash
# Ativar logs debug (se necessário)
oc set env daemonset/resource-governance LOG_LEVEL=DEBUG -n resource-governance

# Ver logs em tempo real
oc logs -f daemonset/resource-governance -n resource-governance --tail=100
```

## 📈 Escalabilidade

### Ajustar Recursos

```bash
# Aumentar recursos do DaemonSet
oc patch daemonset resource-governance -n resource-governance -p '{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "resource-governance",
          "resources": {
            "requests": {"cpu": "200m", "memory": "256Mi"},
            "limits": {"cpu": "1000m", "memory": "1Gi"}
          }
        }]
      }
    }
  }
}'
```

### Ajustar ResourceQuota

```bash
# Aumentar quota do namespace
oc patch resourcequota resource-governance-quota -n resource-governance -p '{
  "spec": {
    "hard": {
      "requests.cpu": "4",
      "requests.memory": "8Gi",
      "limits.cpu": "8",
      "limits.memory": "16Gi"
    }
  }
}'
```

## 🔐 Segurança

### Verificar SecurityContext

```bash
# Verificar se está rodando como usuário não-root
oc get pod <pod-name> -n resource-governance -o jsonpath='{.spec.securityContext}'
```

### Verificar NetworkPolicies

```bash
# Se usando NetworkPolicies, verificar se permite tráfego
oc get networkpolicy -n resource-governance
```

## 📞 Suporte

Para suporte e dúvidas:
- Abra uma issue no [GitHub](https://github.com/andersonid/openshift-resource-governance/issues)
- Consulte a documentação do [OpenShift](https://docs.openshift.com/)
- Verifique os logs da aplicação
