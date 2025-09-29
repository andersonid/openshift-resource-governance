# 🚀 Quick Start - OpenShift Resource Governance Tool

**⚠️ NOTA: Este guia está desatualizado. Use o README.md principal para instruções atuais.**

## ⚡ Deploy em 3 Passos

### 1. Clone o Repositório
```bash
git clone https://github.com/andersonid/openshift-resource-governance.git
cd openshift-resource-governance
```

### 2. Login no OpenShift
```bash
oc login <seu-cluster-openshift>
```

### 3. Deploy Automático
```bash
./openshift-deploy.sh
```

## 🎯 Pronto! 

A aplicação estará disponível em:
- **URL**: `https://resource-governance-route-resource-governance.apps.openshift.local`
- **API**: `https://resource-governance-route-resource-governance.apps.openshift.local/api/v1/cluster/status`

## 📊 O que você terá:

✅ **Dashboard Web** com estatísticas do cluster  
✅ **Validações automáticas** de recursos  
✅ **Relatórios** em JSON, CSV e PDF  
✅ **Integração VPA** para recomendações  
✅ **Integração Prometheus** para métricas reais  

## 🔧 Personalização

Edite o ConfigMap para ajustar:
```bash
oc edit configmap resource-governance-config -n resource-governance
```

## 📚 Documentação Completa

- [README.md](README.md) - Documentação completa
- [DEPLOY.md](DEPLOY.md) - Guia detalhado de deploy
- [GitHub Repository](https://github.com/andersonid/openshift-resource-governance)

## 🆘 Suporte

- **Issues**: [GitHub Issues](https://github.com/andersonid/openshift-resource-governance/issues)
- **Logs**: `oc logs -f daemonset/resource-governance -n resource-governance`
- **Status**: `oc get all -n resource-governance`
