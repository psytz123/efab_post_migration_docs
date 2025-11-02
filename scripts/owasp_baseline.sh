#!/usr/bin/env bash
set -euo pipefail

# Run OWASP ZAP baseline scan against Orders service endpoint.
# Requires Docker.
# Usage: scripts/owasp_baseline.sh http://host.docker.internal:8080

TARGET_URL=${1:-}
if [[ -z "$TARGET_URL" ]]; then
  echo "Usage: $0 <target-url>" >&2
  exit 1
fi

SCAN_NAME="orders-baseline-$(date +%Y%m%d%H%M%S)"
OUTPUT_DIR="reports/owasp"
mkdir -p "$OUTPUT_DIR"

ZAP_IMAGE=${ZAP_DOCKER_IMAGE:-ghcr.io/zaproxy/zaproxy:stable}

CMD=(
  docker run --rm -u "$(id -u):$(id -g)" \
    -v "$PWD/$OUTPUT_DIR:/zap/wrk" \
    "$ZAP_IMAGE" zap-baseline.py \
    -t "$TARGET_URL" \
    -r "$SCAN_NAME.html" \
    -J "$SCAN_NAME.json" \
    -m 50 -z "-config api.disablekey=true"
)

printf 'Running ZAP baseline scan against %s\n' "$TARGET_URL"
"${CMD[@]}"

echo "Baseline scan complete. Reports stored in $OUTPUT_DIR/$SCAN_NAME.*"
