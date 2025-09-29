# 🚀 Deploy Automático - Guia Completo

## 📋 Visão Geral

Este guia explica como configurar deploy automático após o GitHub Actions criar a imagem no Docker Hub.

**⚠️ NOTA: Este guia está desatualizado. Use o README.md principal para instruções atuais.**

## 🔍 **SITUAÇÃO ATUAL:**

### ✅ **GitHub Actions (Funcionando):**
- Builda a imagem automaticamente
- Faz push para Docker Hub
- **NÃO faz deploy no OpenShift**

### ❌ **OpenShift (Manual):**
- **NÃO detecta** mudanças na imagem automaticamente
- Precisa de **rollout manual**
- Blue-Green só funciona se configurado

## 🚀 **SOLUÇÕES PARA DEPLOY AUTOMÁTICO:**

### **Opção 1: Deploy Manual via GitHub Actions** ⭐ (Recomendado)

#### **Como usar:**
1. Vá para: `Actions` → `Deploy to OpenShift (Manual Trigger)`
2. Clique em `Run workflow`
3. Preencha os campos:
   - **OpenShift Server URL**: `https://api.your-cluster.com`
   - **OpenShift Token**: Seu token do OpenShift
   - **Target Namespace**: `resource-governance`
   - **Image Tag**: `latest` ou tag específica
4. Clique em `Run workflow`

#### **Vantagens:**
- ✅ Seguro (requer confirmação manual)
- ✅ Funciona com qualquer cluster OpenShift
- ✅ Controle total sobre quando fazer deploy
- ✅ Logs detalhados no GitHub Actions

---

### **Opção 2: Deploy Automático Local** 🔄

#### **Como usar:**
```bash
# Deploy automático com latest
./scripts/auto-deploy.sh

# Deploy automático com tag específica
./scripts/auto-deploy.sh v1.0.0

# Deploy automático com commit SHA
./scripts/auto-deploy.sh 6f6e4ed19d2fbcccba548eeaf0d9e2624f41afba
```

#### **Vantagens:**
- ✅ Deploy automático
- ✅ Verifica se a imagem existe no Docker Hub
- ✅ Blue-Green deployment (zero downtime)
- ✅ Logs detalhados

#### **Configuração:**
```bash
# 1. Fazer login no OpenShift
oc login https://api.your-cluster.com

# 2. Executar deploy automático
./scripts/auto-deploy.sh latest
```

---

### **Opção 3: Webhook para Deploy Automático** 🌐

#### **Como configurar:**

1. **Instalar dependências:**
```bash
pip install flask
```

2. **Configurar variáveis de ambiente:**
```bash
export IMAGE_NAME="resource-governance"
export REGISTRY="andersonid"
export NAMESPACE="resource-governance"
export AUTO_DEPLOY_SCRIPT="./scripts/auto-deploy.sh"
```

3. **Executar webhook server:**
```bash
python3 scripts/webhook-deploy.py
```

4. **Configurar webhook no Docker Hub:**
   - Acesse: https://hub.docker.com/r/andersonid/resource-governance/webhooks
   - Clique em `Create Webhook`
   - **Webhook URL**: `http://your-server:8080/webhook/dockerhub`
   - **Trigger**: `Push to repository`
   - **Tag**: `latest`

#### **Endpoints disponíveis:**
- `POST /webhook/dockerhub` - Webhook do Docker Hub
- `POST /webhook/github` - Webhook do GitHub
- `POST /deploy/<tag>` - Deploy manual
- `GET /health` - Health check
- `GET /status` - Status do serviço

#### **Vantagens:**
- ✅ Deploy completamente automático
- ✅ Funciona com Docker Hub e GitHub
- ✅ API REST para controle
- ✅ Logs detalhados

---

### **Opção 4: Cron Job para Deploy Automático** ⏰

#### **Como configurar:**

1. **Criar script de verificação:**
```bash
#!/bin/bash
# scripts/check-and-deploy.sh

# Verificar se há nova imagem
LATEST_SHA=$(curl -s "https://api.github.com/repos/andersonid/openshift-resource-governance/commits/main" | jq -r '.sha')
CURRENT_SHA=$(oc get deployment resource-governance -n resource-governance -o jsonpath='{.spec.template.spec.containers[0].image}' | cut -d: -f2)

if [ "$LATEST_SHA" != "$CURRENT_SHA" ]; then
    echo "Nova versão detectada: $LATEST_SHA"
    ./scripts/auto-deploy.sh $LATEST_SHA
else
    echo "Versão já está atualizada: $CURRENT_SHA"
fi
```

2. **Configurar cron job:**
```bash
# Executar a cada 5 minutos
*/5 * * * * /path/to/scripts/check-and-deploy.sh >> /var/log/auto-deploy.log 2>&1
```

#### **Vantagens:**
- ✅ Deploy automático baseado em tempo
- ✅ Verifica mudanças automaticamente
- ✅ Simples de configurar

---

## 🔧 **CONFIGURAÇÃO DO BLUE-GREEN DEPLOYMENT:**

### **Estratégia Rolling Update (Zero Downtime):**
```yaml
# k8s/deployment.yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0  # Nunca derruba pods até o novo estar pronto
      maxSurge: 1        # Permite 1 pod extra durante o rollout
```

### **Health Checks:**
```yaml
# k8s/deployment.yaml
livenessProbe:
  httpGet:
    path: /api/v1/health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /api/v1/health
    port: 8080
  initialDelaySeconds: 15
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 5
  successThreshold: 2
```

---

## 📊 **MONITORAMENTO DO DEPLOY:**

### **Verificar Status:**
```bash
# Status do deployment
oc get deployment resource-governance -n resource-governance

# Status dos pods
oc get pods -n resource-governance -l app.kubernetes.io/name=resource-governance

# Logs do deployment
oc logs -f deployment/resource-governance -n resource-governance

# Histórico de rollouts
oc rollout history deployment/resource-governance -n resource-governance
```

### **Verificar Imagem Atual:**
```bash
# Imagem atual do deployment
oc get deployment resource-governance -n resource-governance -o jsonpath='{.spec.template.spec.containers[0].image}'

# Verificar se a imagem existe no Docker Hub
skopeo inspect docker://andersonid/resource-governance:latest
```

---

## 🚨 **TROUBLESHOOTING:**

### **Problemas Comuns:**

#### 1. **Deploy falha com "ImagePullBackOff"**
```bash
# Verificar se a imagem existe
skopeo inspect docker://andersonid/resource-governance:latest

# Verificar logs do pod
oc describe pod -l app.kubernetes.io/name=resource-governance -n resource-governance
```

#### 2. **Rollout fica travado**
```bash
# Verificar status do rollout
oc rollout status deployment/resource-governance -n resource-governance

# Forçar restart se necessário
oc rollout restart deployment/resource-governance -n resource-governance
```

#### 3. **Webhook não funciona**
```bash
# Verificar logs do webhook
python3 scripts/webhook-deploy.py

# Testar webhook manualmente
curl -X POST http://localhost:8080/deploy/latest
```

---

## 🎯 **RECOMENDAÇÕES:**

### **Para Desenvolvimento:**
- Use **Opção 1** (Deploy Manual via GitHub Actions)
- Controle total sobre quando fazer deploy
- Logs detalhados no GitHub

### **Para Produção:**
- Use **Opção 2** (Deploy Automático Local) com cron job
- Configure webhook para deploy automático
- Monitore logs e status

### **Para Equipes:**
- Use **Opção 3** (Webhook) com API REST
- Configure notificações
- Implemente rollback automático

---

## 🔗 **LINKS ÚTEIS:**

- **GitHub Actions**: https://github.com/andersonid/openshift-resource-governance/actions
- **Docker Hub**: https://hub.docker.com/r/andersonid/resource-governance
- **OpenShift CLI**: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/

---

**Desenvolvido por:** Anderson Nobre  
**Suporte:** Abra uma issue no GitHub se tiver problemas
