# 🚀 GitHub Actions - Guia de Uso

## 📋 Visão Geral

O GitHub Actions está configurado para **buildar e fazer push automático** da imagem Docker para o Docker Hub sempre que você fizer push para o repositório.

## 🔧 Configuração Necessária

### 1. Secrets do GitHub
Certifique-se de que estes secrets estão configurados no repositório:

- `DOCKERHUB_USERNAME`: Seu usuário do Docker Hub
- `DOCKERHUB_TOKEN`: Token de acesso do Docker Hub

**Como configurar:**
1. Vá para: `Settings` → `Secrets and variables` → `Actions`
2. Clique em `New repository secret`
3. Adicione os secrets acima

### 2. Token do Docker Hub
Para criar um token do Docker Hub:
1. Acesse: https://hub.docker.com/settings/security
2. Clique em `New Access Token`
3. Nome: `github-actions`
4. Permissões: `Read, Write, Delete`
5. Copie o token e adicione como `DOCKERHUB_TOKEN`

## 🚀 Como Usar

### 1. Build Automático
**Sempre que você fizer push para `main` ou `develop`:**
- ✅ Build automático da imagem
- ✅ Push para Docker Hub
- ✅ Tag `latest` atualizada

```bash
# Push para main (atualiza latest)
git push origin main

# Push para develop (atualiza develop)
git push origin develop
```

### 2. Releases com Tags
**Para criar uma release:**

```bash
# Usar o script de release
./scripts/release.sh patch    # 1.0.0 -> 1.0.1
./scripts/release.sh minor    # 1.0.0 -> 1.1.0
./scripts/release.sh major    # 1.0.0 -> 2.0.0
./scripts/release.sh custom 2.0.0-beta.1

# Ou criar tag manualmente
git tag v1.0.0
git push origin v1.0.0
```

### 3. Build Manual
**Para buildar manualmente:**
1. Vá para: `Actions` → `Build and Push Image to Docker Hub`
2. Clique em `Run workflow`
3. Escolha a branch
4. Opcionalmente, defina uma tag customizada
5. Clique em `Run workflow`

## 📦 Tags Geradas

### Branch `main`
- `andersonid/resource-governance:latest` (sempre atualizada)
- `andersonid/resource-governance:COMMIT_SHA` (específica do commit)

### Branch `develop`
- `andersonid/resource-governance:develop` (sempre atualizada)
- `andersonid/resource-governance:develop-COMMIT_SHA` (específica do commit)

### Tags (ex: v1.0.0)
- `andersonid/resource-governance:v1.0.0` (específica da tag)
- `andersonid/resource-governance:latest` (atualizada)

### Pull Requests
- `andersonid/resource-governance:pr-COMMIT_SHA` (apenas para teste)

## 🔍 Monitoramento

### Verificar Status do Build
```bash
# Listar últimos builds
gh run list --repo andersonid/openshift-resource-governance --workflow="build-only.yml"

# Ver logs de um build específico
gh run view RUN_ID --repo andersonid/openshift-resource-governance --log

# Ver status em tempo real
gh run watch --repo andersonid/openshift-resource-governance
```

### Verificar Imagens no Docker Hub
- **Docker Hub**: https://hub.docker.com/r/andersonid/resource-governance/tags
- **GitHub Releases**: https://github.com/andersonid/openshift-resource-governance/releases

## 🛠️ Troubleshooting

### Build Falhou
1. **Verificar logs:**
   ```bash
   gh run view RUN_ID --repo andersonid/openshift-resource-governance --log-failed
   ```

2. **Problemas comuns:**
   - **Docker Hub login falhou**: Verificar `DOCKERHUB_TOKEN`
   - **Build falhou**: Verificar sintaxe do código Python
   - **Push falhou**: Verificar permissões do token

### Imagem Não Atualizada
1. **Verificar se o build foi concluído:**
   ```bash
   gh run list --repo andersonid/openshift-resource-governance --workflow="build-only.yml" --status=completed
   ```

2. **Verificar tags no Docker Hub:**
   ```bash
   docker pull andersonid/resource-governance:latest
   docker inspect andersonid/resource-governance:latest
   ```

### Rebuild Manual
Se precisar rebuildar uma versão específica:
```bash
# Fazer push vazio para triggerar build
git commit --allow-empty -m "Trigger rebuild"
git push origin main
```

## 📊 Workflow Detalhado

### 1. Trigger
- **Push para main/develop**: Build automático
- **Tag push**: Build + Release
- **Pull Request**: Build para teste
- **Manual dispatch**: Build com tag customizada

### 2. Build Process
1. **Checkout** do código
2. **Syntax check** do Python
3. **Setup Podman** (Docker alternative)
4. **Login** no Docker Hub
5. **Determine tags** baseado no trigger
6. **Build** da imagem com cache
7. **Tag** da imagem
8. **Push** para Docker Hub
9. **Create release** (se for tag)

### 3. Output
- **Imagem Docker** disponível no Docker Hub
- **GitHub Release** (se for tag)
- **Logs detalhados** no GitHub Actions

## 🎯 Melhores Práticas

### 1. Versionamento
- Use **semantic versioning** (ex: 1.0.0, 1.0.1, 1.1.0)
- Use o script `./scripts/release.sh` para releases
- Teste em `develop` antes de fazer merge para `main`

### 2. Deploy
- Use `andersonid/resource-governance:latest` para desenvolvimento
- Use `andersonid/resource-governance:v1.0.0` para produção
- Sempre teste a imagem antes de fazer deploy em produção

### 3. Monitoramento
- Verifique os logs do GitHub Actions regularmente
- Monitore o Docker Hub para verificar se as imagens estão sendo atualizadas
- Use `gh` CLI para monitoramento rápido

## 🔗 Links Úteis

- **GitHub Actions**: https://github.com/andersonid/openshift-resource-governance/actions
- **Docker Hub**: https://hub.docker.com/r/andersonid/resource-governance
- **GitHub Releases**: https://github.com/andersonid/openshift-resource-governance/releases
- **Workflow File**: `.github/workflows/build-only.yml`

---

**Desenvolvido por:** Anderson Nobre  
**Suporte:** Abra uma issue no GitHub se tiver problemas
