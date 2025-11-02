#!/usr/bin/env bash
#
# OTA Manifest Generator
# Generates signed OTA manifest with component digests, rollback metadata, and safety checks
# Implements ADR-007: Edge OTA & Signing Policy
#
# Usage:
#   generate-ota-manifest.sh --digests-file <file> --version <version> --commit <sha> --output <file>
#

set -euo pipefail

# Default values
DIGESTS_FILE=""
VERSION=""
COMMIT=""
OUTPUT_FILE="ota-manifest.json"
ROLLBACK_REF=""
POLICY_VERSION="1.0.0"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Usage information
usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Generate OTA manifest with component digests and safety metadata

OPTIONS:
    --digests-file FILE     Path to file containing component digests
    --version VERSION       Release version (e.g., v1.2.3)
    --commit SHA            Git commit SHA
    --output FILE           Output manifest file (default: ota-manifest.json)
    --rollback-ref REF      Reference to previous manifest for rollback
    --policy-version VER    Policy version (default: 1.0.0)
    -h, --help              Show this help message

EXAMPLES:
    $0 --digests-file digests.txt --version v1.2.3 --commit abc123 --output manifest.json
    $0 --digests-file digests.txt --version v1.2.3 --commit abc123 --rollback-ref v1.2.2

DIGEST FILE FORMAT:
    Each line should contain: component_name=sha256:digest
    Example:
        edge-agent=sha256:abc123...
        opc-ua-adapter=sha256:def456...
EOF
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --digests-file)
            DIGESTS_FILE="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --commit)
            COMMIT="$2"
            shift 2
            ;;
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --rollback-ref)
            ROLLBACK_REF="$2"
            shift 2
            ;;
        --policy-version)
            POLICY_VERSION="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required arguments
if [[ -z "$DIGESTS_FILE" ]]; then
    log_error "Missing required argument: --digests-file"
    usage
fi

if [[ -z "$VERSION" ]]; then
    log_error "Missing required argument: --version"
    usage
fi

if [[ -z "$COMMIT" ]]; then
    log_error "Missing required argument: --commit"
    usage
fi

# Validate digests file exists
if [[ ! -f "$DIGESTS_FILE" ]]; then
    log_error "Digests file not found: $DIGESTS_FILE"
    exit 1
fi

log_info "Generating OTA manifest..."
log_info "Version: $VERSION"
log_info "Commit: $COMMIT"
log_info "Digests file: $DIGESTS_FILE"

# Generate timestamp in ISO 8601 format
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Initialize manifest JSON structure
cat > "$OUTPUT_FILE" <<EOF
{
  "manifest_version": "1.0",
  "policy_version": "$POLICY_VERSION",
  "version": "$VERSION",
  "commit": "$COMMIT",
  "timestamp": "$TIMESTAMP",
  "components": [],
  "rollback_reference": "$ROLLBACK_REF",
  "safety": {
    "requires_plc_approval": true,
    "max_rollout_percentage": 10,
    "health_check_timeout_seconds": 300,
    "auto_rollback_on_failure": true
  },
  "metadata": {
    "builder": "github-actions",
    "build_url": "${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-unknown}/actions/runs/${GITHUB_RUN_ID:-unknown}",
    "signing_method": "cosign-keyless-oidc"
  }
}
EOF

log_info "Base manifest created"

# Read component digests and add to manifest
log_info "Processing component digests..."

COMPONENT_COUNT=0

while IFS='=' read -r COMPONENT DIGEST; do
    # Skip empty lines and comments
    [[ -z "$COMPONENT" || "$COMPONENT" =~ ^# ]] && continue

    # Trim whitespace
    COMPONENT=$(echo "$COMPONENT" | xargs)
    DIGEST=$(echo "$DIGEST" | xargs)

    # Validate digest format (should be sha256:...)
    if [[ ! "$DIGEST" =~ ^sha256:[a-f0-9]{64}$ ]]; then
        log_warn "Invalid digest format for $COMPONENT: $DIGEST (expected sha256:...)"
        continue
    fi

    log_info "Adding component: $COMPONENT ($DIGEST)"

    # Add component to manifest using jq
    jq --arg name "$COMPONENT" \
       --arg digest "$DIGEST" \
       --arg timestamp "$TIMESTAMP" \
       '.components += [{
           "name": $name,
           "digest": $digest,
           "type": "container",
           "updated_at": $timestamp
       }]' "$OUTPUT_FILE" > "${OUTPUT_FILE}.tmp"

    mv "${OUTPUT_FILE}.tmp" "$OUTPUT_FILE"

    ((COMPONENT_COUNT++))
done < "$DIGESTS_FILE"

log_info "Added $COMPONENT_COUNT components to manifest"

# Validate manifest has at least one component
if [[ $COMPONENT_COUNT -eq 0 ]]; then
    log_error "No valid components found in digests file"
    exit 1
fi

# Generate manifest checksum
MANIFEST_CHECKSUM=$(sha256sum "$OUTPUT_FILE" | cut -d' ' -f1)

# Add checksum to metadata
jq --arg checksum "sha256:$MANIFEST_CHECKSUM" \
   '.metadata.manifest_checksum = $checksum' "$OUTPUT_FILE" > "${OUTPUT_FILE}.tmp"

mv "${OUTPUT_FILE}.tmp" "$OUTPUT_FILE"

log_info "Manifest checksum: sha256:$MANIFEST_CHECKSUM"

# Validate final manifest structure
log_info "Validating manifest structure..."

REQUIRED_FIELDS=(
    "manifest_version"
    "policy_version"
    "version"
    "commit"
    "timestamp"
    "components"
    "safety"
    "metadata"
)

for FIELD in "${REQUIRED_FIELDS[@]}"; do
    if ! jq -e ".$FIELD" "$OUTPUT_FILE" > /dev/null 2>&1; then
        log_error "Missing required field: $FIELD"
        exit 1
    fi
done

# Validate safety settings
if ! jq -e '.safety.requires_plc_approval' "$OUTPUT_FILE" > /dev/null 2>&1; then
    log_error "Safety configuration missing: requires_plc_approval"
    exit 1
fi

# Validate at least one component
COMPONENT_COUNT=$(jq '.components | length' "$OUTPUT_FILE")
if [[ $COMPONENT_COUNT -eq 0 ]]; then
    log_error "Manifest has no components"
    exit 1
fi

log_info "Manifest validation passed"

# Pretty print manifest
log_info "Generated OTA manifest:"
echo "================================"
jq '.' "$OUTPUT_FILE"
echo "================================"

log_info "OTA manifest saved to: $OUTPUT_FILE"
log_info "Components: $COMPONENT_COUNT"
log_info "Ready for signing with Cosign"

# Generate manifest summary
cat > "${OUTPUT_FILE}.summary" <<EOF
OTA Manifest Summary
====================
Version: $VERSION
Commit: $COMMIT
Timestamp: $TIMESTAMP
Components: $COMPONENT_COUNT
Rollback Reference: $ROLLBACK_REF
Policy Version: $POLICY_VERSION
Manifest Checksum: sha256:$MANIFEST_CHECKSUM

Components:
$(jq -r '.components[] | "  - \(.name): \(.digest)"' "$OUTPUT_FILE")

Safety Configuration:
  - PLC Approval Required: $(jq -r '.safety.requires_plc_approval' "$OUTPUT_FILE")
  - Max Rollout: $(jq -r '.safety.max_rollout_percentage' "$OUTPUT_FILE")%
  - Health Check Timeout: $(jq -r '.safety.health_check_timeout_seconds' "$OUTPUT_FILE")s
  - Auto Rollback: $(jq -r '.safety.auto_rollback_on_failure' "$OUTPUT_FILE")

Metadata:
  - Builder: $(jq -r '.metadata.builder' "$OUTPUT_FILE")
  - Signing Method: $(jq -r '.metadata.signing_method' "$OUTPUT_FILE")
EOF

log_info "Summary saved to: ${OUTPUT_FILE}.summary"
log_info "Done!"

exit 0
