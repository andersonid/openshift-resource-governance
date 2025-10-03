#!/bin/bash

# Script to create releases and tags for OpenShift Resource Governance

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to show help
show_help() {
    echo "OpenShift Resource Governance - Release Script"
    echo "=============================================="
    echo ""
    echo "Usage: $0 [COMMAND] [VERSION]"
    echo ""
    echo "Commands:"
    echo "  patch     Create patch release (ex: 1.0.0 -> 1.0.1)"
    echo "  minor     Create minor release (ex: 1.0.0 -> 1.1.0)"
    echo "  major     Create major release (ex: 1.0.0 -> 2.0.0)"
    echo "  custom    Create release with custom version"
    echo "  list      List existing releases"
    echo "  help      Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 patch                    # 1.0.0 -> 1.0.1"
    echo "  $0 minor                    # 1.0.0 -> 1.1.0"
    echo "  $0 custom 2.0.0-beta.1     # Custom version"
    echo "  $0 list                     # List releases"
    echo ""
}

# Function to get current version
get_current_version() {
    local latest_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
    echo "${latest_tag#v}"  # Remove 'v' prefix
}

# Function to increment version
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

# Function to validate version
validate_version() {
    local version=$1
    if [[ ! $version =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?$ ]]; then
        echo -e "${RED}ERROR: Invalid version: $version${NC}"
        echo "Expected format: X.Y.Z or X.Y.Z-suffix"
        exit 1
    fi
}

# Function to create release
create_release() {
    local version=$1
    local tag="v$version"
    
    echo -e "${BLUE}Creating release $tag${NC}"
    echo ""
    
    # Check if already exists
    if git tag -l | grep -q "^$tag$"; then
        echo -e "${RED}ERROR: Tag $tag already exists!${NC}"
        exit 1
    fi
    
    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        echo -e "${YELLOW}WARNING: There are uncommitted changes. Continue? (y/N)${NC}"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            echo "Cancelled."
            exit 1
        fi
    fi
    
    # Commit changes if any
    if ! git diff-index --quiet HEAD --; then
        echo -e "${BLUE}Committing changes...${NC}"
        git add .
        git commit -m "Release $tag"
    fi
    
    # Create tag
    echo -e "${BLUE}Creating tag $tag...${NC}"
    git tag -a "$tag" -m "Release $tag"
    
    # Push tag
    echo -e "${BLUE}Pushing tag...${NC}"
    git push origin "$tag"
    
    echo ""
    echo -e "${GREEN}SUCCESS: Release $tag created successfully!${NC}"
    echo ""
    echo "Useful links:"
    echo "   GitHub: https://github.com/andersonid/openshift-resource-governance/releases/tag/$tag"
    echo "   Quay.io: https://quay.io/repository/rh_ee_anobre/resource-governance"
    echo ""
    echo "GitHub Actions will automatically:"
    echo "   1. Build container image"
    echo "   2. Push to Quay.io"
    echo "   3. Create GitHub release"
    echo ""
    echo "Wait a few minutes and check:"
    echo "   gh run list --repo andersonid/openshift-resource-governance --workflow='build-only.yml'"
}

# Function to list releases
list_releases() {
    echo -e "${BLUE}Existing releases:${NC}"
    echo ""
    git tag -l --sort=-version:refname | head -10
    echo ""
    echo "To see all: git tag -l --sort=-version:refname"
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
            echo -e "${RED}ERROR: Custom version not provided!${NC}"
            echo "Usage: $0 custom 2.0.0-beta.1"
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
