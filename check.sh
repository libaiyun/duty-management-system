#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo "========================================="
echo "  CI Check Script"
echo "========================================="
echo ""

run_step() {
    local label="$1"
    shift
    echo "--- $label ---"
    if "$@"; then
        echo "✓ $label passed"
    else
        echo "✗ $label failed"
        exit 1
    fi
    echo ""
}

# ── Backend (via Docker Compose) ──
echo ">>> Starting backend services..."
docker compose up -d db redis backend --wait

run_step "Backend lint (flake8)"        docker compose run --rm --no-deps backend flake8 backend/app
run_step "Backend type-check (mypy)"    docker compose run --rm --no-deps backend mypy
run_step "Backend test (pytest)"        docker compose run --rm --no-deps backend pytest

echo ">>> Stopping backend services..."
docker compose down -v

# ── Frontend (local) ──
run_step "Frontend lint (eslint)"       npm --prefix frontend run lint
run_step "Frontend type-check (tsc)"    npm --prefix frontend run type-check
run_step "Frontend build (vite)"        npm --prefix frontend run build

echo "========================================="
echo "  All CI checks passed"
echo "========================================="
