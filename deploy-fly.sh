#!/usr/bin/env bash
# =============================================================================
# Agus OSINT — Fly.io Deployment Script
# =============================================================================
# Prerequisites:
#   1. Install flyctl: curl -L https://fly.io/install.sh | sh
#   2. Sign up (free): fly auth signup
#   3. Run this script: bash deploy-fly.sh
# =============================================================================

set -euo pipefail

BACKEND_APP="agus-backend"
FRONTEND_APP="agus-frontend"
REGION="iad"  # US East (Virginia) — change to your nearest region

echo "============================================"
echo "  Agus OSINT — Fly.io Deployment"
echo "============================================"
echo ""

# --- Check flyctl is installed ---
if ! command -v fly &> /dev/null; then
    echo "ERROR: flyctl not installed."
    echo "Install: curl -L https://fly.io/install.sh | sh"
    echo "  or: powershell -Command \"iwr https://fly.io/install.ps1 -useb | iex\""
    exit 1
fi

# --- Check auth ---
if ! fly auth whoami &> /dev/null 2>&1; then
    echo "Not logged in. Running 'fly auth login'..."
    fly auth login
fi

echo "Logged in as: $(fly auth whoami)"
echo ""

# =============================================================================
# Step 1: Deploy Backend
# =============================================================================
echo ">>> Step 1: Deploying backend ($BACKEND_APP)..."

# Create app if it doesn't exist
if ! fly apps list | grep -q "$BACKEND_APP"; then
    echo "Creating app: $BACKEND_APP"
    fly apps create "$BACKEND_APP" --machines
fi

# Deploy backend
cd backend
fly deploy --app "$BACKEND_APP" --yes
cd ..

echo ""
echo "Backend live at: https://$BACKEND_APP.fly.dev"
echo "Health check:    https://$BACKEND_APP.fly.dev/api/health"
echo ""

# Wait for backend to be healthy
echo "Waiting for backend health check (prefetch takes ~2min)..."
for i in $(seq 1 30); do
    if curl -sf "https://$BACKEND_APP.fly.dev/api/health" > /dev/null 2>&1; then
        echo "Backend is healthy!"
        break
    fi
    echo "  Waiting... ($i/30)"
    sleep 10
done

# =============================================================================
# Step 2: Deploy Frontend
# =============================================================================
echo ""
echo ">>> Step 2: Deploying frontend ($FRONTEND_APP)..."

# Create app if it doesn't exist
if ! fly apps list | grep -q "$FRONTEND_APP"; then
    echo "Creating app: $FRONTEND_APP"
    fly apps create "$FRONTEND_APP" --machines
fi

# Deploy frontend (VITE_API_BASE is set in fly.toml build.args)
cd frontend
fly deploy --app "$FRONTEND_APP" --yes
cd ..

echo ""
echo "============================================"
echo "  DEPLOYMENT COMPLETE"
echo "============================================"
echo ""
echo "  Frontend: https://$FRONTEND_APP.fly.dev"
echo "  Backend:  https://$BACKEND_APP.fly.dev"
echo "  Health:   https://$BACKEND_APP.fly.dev/api/health"
echo ""
echo "  Optional: Set API keys for extra layers:"
echo "    fly secrets set ACLED_EMAIL=you@email.com -a $BACKEND_APP"
echo "    fly secrets set ACLED_PASSWORD=yourpass -a $BACKEND_APP"
echo "    fly secrets set WINDY_API_KEY=yourkey -a $BACKEND_APP"
echo "    fly secrets set OTX_API_KEY=yourkey -a $BACKEND_APP"
echo ""
echo "  Monitor logs:"
echo "    fly logs -a $BACKEND_APP"
echo "    fly logs -a $FRONTEND_APP"
echo ""
echo "  To redeploy after changes:"
echo "    cd backend && fly deploy"
echo "    cd frontend && fly deploy"
echo "============================================"
