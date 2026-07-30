#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# init.sh — REC Stack Bootstrap
# Starts all services and prints service URLs.
# Usage: bash init.sh
# ──────────────────────────────────────────────────────────────────────────────

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}${CYAN}"
echo "  ██████╗ ███████╗ ██████╗"
echo "  ██╔══██╗██╔════╝██╔════╝"
echo "  ██████╔╝█████╗  ██║     "
echo "  ██╔══██╗██╔══╝  ██║     "
echo "  ██║  ██║███████╗╚██████╗"
echo "  ╚═╝  ╚═╝╚══════╝ ╚═════╝"
echo -e "${NC}"
echo -e "${BOLD}Real-time Event Capture — Stack Bootstrap${NC}"
echo "────────────────────────────────────────"

# Check .env
if [ ! -f .env ]; then
    echo -e "${RED}⚠  .env not found — copying from .env.example${NC}"
    cp .env.example .env
    echo -e "${RED}   Edit .env and set real secrets before production use!${NC}"
fi

# Pull / build images
echo -e "\n${CYAN}→ Building images...${NC}"
docker compose build --quiet

# Start infrastructure first
echo -e "${CYAN}→ Starting infrastructure (postgres, redis, minio)...${NC}"
docker compose up -d postgres redis minio
echo -e "${CYAN}  Waiting for postgres healthcheck...${NC}"
docker compose wait postgres

# Start cloud backend
echo -e "${CYAN}→ Starting cloud backend (api-gateway, embedding-worker, celery-beat)...${NC}"
docker compose up -d api-gateway embedding-worker celery-beat

# Start monitoring
echo -e "${CYAN}→ Starting monitoring (prometheus, grafana)...${NC}"
docker compose up -d prometheus grafana

# Start portal
echo -e "${CYAN}→ Starting portal...${NC}"
docker compose up -d portal

# Start edge node (optional — skipped if no GPU/USB camera)
if [ "${SKIP_EDGE:-false}" != "true" ]; then
    echo -e "${CYAN}→ Starting edge node services...${NC}"
    docker compose up -d camera-controller detection-engine capture-orchestrator
fi

echo ""
echo -e "${GREEN}${BOLD}✅ REC Stack is running!${NC}"
echo "────────────────────────────────────────"
echo -e "  ${BOLD}API Gateway:${NC}     http://localhost:8000"
echo -e "  ${BOLD}API Docs:${NC}        http://localhost:8000/docs"
echo -e "  ${BOLD}User Portal:${NC}     http://localhost:3000"
echo -e "  ${BOLD}MinIO Console:${NC}   http://localhost:9001"
echo -e "  ${BOLD}Prometheus:${NC}      http://localhost:9090"
echo -e "  ${BOLD}Grafana:${NC}         http://localhost:3001"
echo "────────────────────────────────────────"
echo -e "  Stop all: ${CYAN}docker compose down${NC}"
echo ""
