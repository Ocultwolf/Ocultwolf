#!/usr/bin/env bash
[ -f .env ] && export $(grep -v '^#' .env | xargs)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
IMAGE_NAME="${OPENCLAW_IMAGE:-alpine/openclaw:latest}"

# Dependencias
command -v docker >/dev/null 2>&1 || { echo "Docker no instalado"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 no disponible"; exit 1; }

# Crear carpetas locales
mkdir -p "${OPENCLAW_CONFIG_DIR:-$HOME/.openclaw}"
mkdir -p "${OPENCLAW_WORKSPACE_DIR:-$HOME/.openclaw/workspace}"

# Export variables
export OPENCLAW_CONFIG_DIR
export OPENCLAW_WORKSPACE_DIR
export OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
export OPENCLAW_BRIDGE_PORT="${OPENCLAW_BRIDGE_PORT:-18790}"
export OPENCLAW_GATEWAY_BIND="${OPENCLAW_GATEWAY_BIND:-lan}"
export OPENCLAW_IMAGE="$IMAGE_NAME"
export OPENCLAW_GATEWAY_TOKEN

# Onboarding interactivo
echo "==> Onboarding OpenClaw (solo la primera vez)"
echo "  Gateway bind: lan"
echo "  Gateway auth: token"
echo "  Gateway token: $OPENCLAW_GATEWAY_TOKEN"
echo "  Tailscale exposure: Off"
echo "  Install Gateway daemon: No"
docker compose -f "$COMPOSE_FILE" run --rm openclaw-cli onboard --no-install-daemon

# Login WhatsApp (QR)
echo "==> Conectar WhatsApp (escanea QR)"
docker compose -f "$COMPOSE_FILE" run --rm openclaw-cli channels login

# Arrancar Gateway
echo "==> Levantando OpenClaw Gateway"
docker compose -f "$COMPOSE_FILE" up -d openclaw-gateway

# Instrucciones finales
echo ""
echo "Gateway corriendo en el puerto ${OPENCLAW_GATEWAY_PORT} (accesible via Tailscale)"
echo "Config: $OPENCLAW_CONFIG_DIR"
echo "Workspace: $OPENCLAW_WORKSPACE_DIR"
echo "Token: $OPENCLAW_GATEWAY_TOKEN"
echo ""
echo "Comandos útiles:"
echo "  docker compose logs -f openclaw-gateway"
echo "  docker compose exec openclaw-gateway node dist/index.js health --token \"$OPENCLAW_GATEWAY_TOKEN\""
