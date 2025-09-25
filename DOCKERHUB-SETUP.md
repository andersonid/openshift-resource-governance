# 🐳 Configuração do Docker Hub

## 📋 Secrets Necessários no GitHub

Para o GitHub Actions funcionar com Docker Hub, configure estes secrets:

### 1. **DOCKERHUB_USERNAME**
- **Nome**: `DOCKERHUB_USERNAME`
- **Valor**: `andersonid`

### 2. **DOCKERHUB_TOKEN**
- **Nome**: `DOCKERHUB_TOKEN`
- **Valor**: Seu token de acesso do Docker Hub

## 🔑 Como Obter o Token do Docker Hub

### 1. **Acesse o Docker Hub**
- Vá para: https://hub.docker.com
- Faça login com sua conta

### 2. **Criar Access Token**
- Clique no seu avatar (canto superior direito)
- Vá em **Account Settings**
- Clique em **Security** → **New Access Token**
- Dê um nome: `openshift-resource-governance`
- Selecione **Read, Write, Delete** permissions
- Clique em **Generate**
- **Copie o token** (você só verá uma vez!)

### 3. **Configurar no GitHub**
- Vá para: https://github.com/andersonid/openshift-resource-governance/settings/secrets/actions
- Clique em **New repository secret**
- Adicione os dois secrets acima

## 🚀 Deploy Automático

Após configurar os secrets, o deploy será automático:

1. **Push para main** → GitHub Actions executa
2. **Build da imagem** → `andersonid/openshift-resource-governance:latest`
3. **Push para Docker Hub** → Imagem disponível publicamente
4. **Deploy no OpenShift** → Aplicação atualizada

## 🔧 Deploy Manual (Alternativo)

Se preferir deploy manual:

```bash
# 1. Build local
./scripts/build.sh

# 2. Login no Docker Hub
docker login

# 3. Push da imagem
docker push andersonid/openshift-resource-governance:latest

# 4. Deploy no OpenShift
./openshift-deploy.sh
```

## 📊 Verificar Deploy

```bash
# Ver imagem no Docker Hub
# https://hub.docker.com/r/andersonid/openshift-resource-governance

# Ver status no OpenShift
oc get all -n resource-governance

# Ver logs
oc logs -f daemonset/resource-governance -n resource-governance
```

## 🐛 Troubleshooting

### Erro de Login Docker Hub
```bash
# Verificar se está logado
docker login

# Testar push manual
docker push andersonid/openshift-resource-governance:latest
```

### Erro de Permissão GitHub Actions
- Verifique se os secrets estão configurados corretamente
- Verifique se o token tem permissões de Read, Write, Delete
- Verifique se o usuário tem acesso ao repositório Docker Hub

### Imagem não encontrada no OpenShift
```bash
# Verificar se a imagem existe
docker pull andersonid/openshift-resource-governance:latest

# Verificar logs do pod
oc describe pod <pod-name> -n resource-governance
```

## 📝 Notas Importantes

- **Imagem pública**: A imagem será pública no Docker Hub
- **Tags automáticas**: GitHub Actions cria tags baseadas no commit
- **Cache**: Docker Hub mantém cache das imagens
- **Limites**: Docker Hub tem limites de pull/push (verifique seu plano)

## 🔄 Atualizações

Para atualizar a aplicação:

```bash
# 1. Fazer mudanças no código
git add .
git commit -m "Update application"
git push origin main

# 2. GitHub Actions fará o resto automaticamente!
# - Build da nova imagem
# - Push para Docker Hub
# - Deploy no OpenShift
```

## 📞 Suporte

- **Docker Hub**: https://hub.docker.com/r/andersonid/openshift-resource-governance
- **GitHub**: https://github.com/andersonid/openshift-resource-governance
- **Issues**: https://github.com/andersonid/openshift-resource-governance/issues
