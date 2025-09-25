#!/bin/bash

# Script para criar releases e tags do OpenShift Resource Governance

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para mostrar ajuda
show_help() {
    echo "🚀 OpenShift Resource Governance - Release Script"
    echo "=================================================="
    echo ""
    echo "Uso: $0 [COMANDO] [VERSÃO]"
    echo ""
    echo "Comandos:"
    echo "  patch     Criar release patch (ex: 1.0.0 -> 1.0.1)"
    echo "  minor     Criar release minor (ex: 1.0.0 -> 1.1.0)"
    echo "  major     Criar release major (ex: 1.0.0 -> 2.0.0)"
    echo "  custom    Criar release com versão customizada"
    echo "  list      Listar releases existentes"
    echo "  help      Mostrar esta ajuda"
    echo ""
    echo "Exemplos:"
    echo "  $0 patch                    # 1.0.0 -> 1.0.1"
    echo "  $0 minor                    # 1.0.0 -> 1.1.0"
    echo "  $0 custom 2.0.0-beta.1     # Versão customizada"
    echo "  $0 list                     # Listar releases"
    echo ""
}

# Função para obter a versão atual
get_current_version() {
    local latest_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
    echo "${latest_tag#v}"  # Remove o 'v' do início
}

# Função para incrementar versão
increment_version() {
    local version=$1
    local type=$2
    
    IFS='.' read -ra VERSION_PARTS <<< "$version"
    local major=${VERSION_PARTS[0]}
    local minor=${VERSION_PARTS[1]}
    local patch=${VERSION_PARTS[2]}
    
    case $type in
        "major")
            echo "$((major + 1)).0.0"
            ;;
        "minor")
            echo "$major.$((minor + 1)).0"
            ;;
        "patch")
            echo "$major.$minor.$((patch + 1))"
            ;;
        *)
            echo "$version"
            ;;
    esac
}

# Função para validar versão
validate_version() {
    local version=$1
    if [[ ! $version =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?$ ]]; then
        echo -e "${RED}❌ Versão inválida: $version${NC}"
        echo "Formato esperado: X.Y.Z ou X.Y.Z-suffix"
        exit 1
    fi
}

# Função para criar release
create_release() {
    local version=$1
    local tag="v$version"
    
    echo -e "${BLUE}🚀 Criando release $tag${NC}"
    echo ""
    
    # Verificar se já existe
    if git tag -l | grep -q "^$tag$"; then
        echo -e "${RED}❌ Tag $tag já existe!${NC}"
        exit 1
    fi
    
    # Verificar se há mudanças não commitadas
    if ! git diff-index --quiet HEAD --; then
        echo -e "${YELLOW}⚠️  Há mudanças não commitadas. Deseja continuar? (y/N)${NC}"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            echo "Cancelado."
            exit 1
        fi
    fi
    
    # Fazer commit das mudanças se houver
    if ! git diff-index --quiet HEAD --; then
        echo -e "${BLUE}📝 Fazendo commit das mudanças...${NC}"
        git add .
        git commit -m "Release $tag"
    fi
    
    # Criar tag
    echo -e "${BLUE}🏷️  Criando tag $tag...${NC}"
    git tag -a "$tag" -m "Release $tag"
    
    # Push da tag
    echo -e "${BLUE}📤 Fazendo push da tag...${NC}"
    git push origin "$tag"
    
    echo ""
    echo -e "${GREEN}✅ Release $tag criado com sucesso!${NC}"
    echo ""
    echo "🔗 Links úteis:"
    echo "   GitHub: https://github.com/andersonid/openshift-resource-governance/releases/tag/$tag"
    echo "   Docker Hub: https://hub.docker.com/r/andersonid/resource-governance/tags"
    echo ""
    echo "🚀 O GitHub Actions irá automaticamente:"
    echo "   1. Buildar a imagem Docker"
    echo "   2. Fazer push para Docker Hub"
    echo "   3. Criar release no GitHub"
    echo ""
    echo "⏳ Aguarde alguns minutos e verifique:"
    echo "   gh run list --repo andersonid/openshift-resource-governance --workflow='build-only.yml'"
}

# Função para listar releases
list_releases() {
    echo -e "${BLUE}📋 Releases existentes:${NC}"
    echo ""
    git tag -l --sort=-version:refname | head -10
    echo ""
    echo "💡 Para ver todos: git tag -l --sort=-version:refname"
}

# Main
case "${1:-help}" in
    "patch")
        current_version=$(get_current_version)
        new_version=$(increment_version "$current_version" "patch")
        validate_version "$new_version"
        create_release "$new_version"
        ;;
    "minor")
        current_version=$(get_current_version)
        new_version=$(increment_version "$current_version" "minor")
        validate_version "$new_version"
        create_release "$new_version"
        ;;
    "major")
        current_version=$(get_current_version)
        new_version=$(increment_version "$current_version" "major")
        validate_version "$new_version"
        create_release "$new_version"
        ;;
    "custom")
        if [ -z "$2" ]; then
            echo -e "${RED}❌ Versão customizada não fornecida!${NC}"
            echo "Uso: $0 custom 2.0.0-beta.1"
            exit 1
        fi
        validate_version "$2"
        create_release "$2"
        ;;
    "list")
        list_releases
        ;;
    "help"|*)
        show_help
        ;;
esac
