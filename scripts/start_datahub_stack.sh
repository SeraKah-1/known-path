#!/usr/bin/env bash
# Start the best available local DataHub path for this machine.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${PATH}:/data/data/com.termux/files/usr/bin:/usr/bin"

echo "==> Checking Docker (required for official DataHub quickstart)..."
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "Docker OK — installing CLI if needed and running quickstart..."
  python3 -m pip install -q --upgrade 'acryl-datahub' || true
  if python3 -m datahub version >/dev/null 2>&1; then
    python3 -m datahub docker quickstart
    echo ""
    echo "UI:  http://localhost:9002  (user: datahub / pass: datahub)"
    echo "GMS: http://localhost:8080"
    echo "Then: datahub init --username datahub --password datahub"
    echo "      datahub datapack load showcase-ecommerce"
    exit 0
  fi
fi

echo "Docker not available or not running."
echo "==> Starting mini-gms stand-in on :8080 for known-path tool tests..."
exec python3 "$ROOT/scripts/mini_gms.py" 8080
