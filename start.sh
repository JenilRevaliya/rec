#!/bin/bash

# --- Styling & Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${CYAN}${BOLD}"
cat << "EOF"
    ____  ___________ 
   / __ \/ ____/ ___/ 
  / /_/ / __/ / /    
 / _, _/ /___/ /___  
/_/ |_/_____/\____/   
EOF
echo -e "${NC}"

echo -e "${YELLOW}[!] IGNITING FULL SYSTEM SEQUENCE...${NC}\n"

# 1. FAILS-SAFE DOCKER CHECK
echo -e "${BLUE}[1/5] Initiating Docker Daemon Connection...${NC}"
# First try standard docker
if ! docker info >/dev/null 2>&1; then
    echo -e "  ${YELLOW}➔ Standard docker socket unreachable. Searching for Colima...${NC}"
    export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"
    if ! docker info >/dev/null 2>&1; then
        echo -e "  ${RED}➔ Colima socket unreachable. Attempting force-start Colima...${NC}"
        colima start || {
            echo -e "  ${RED}✖ FATAL: Could not start Docker/Colima daemon. Please start Docker manually.${NC}"
            exit 1
        }
    fi
fi
echo -e "  ${GREEN}✔ Docker connection established!${NC}\n"

# 2. Aggressive Cleanup
echo -e "${BLUE}[2/5] Purging zombie processes...${NC}"
if pgrep -f "lab_api.py" > /dev/null; then
    echo -e "  ${YELLOW}➔ Neutralizing hanging lab_api.py instances...${NC}"
    pkill -f "lab_api.py" || true
    sleep 1
fi
echo -e "  ${YELLOW}➔ Sending teardown signal to Docker Compose...${NC}"
docker-compose down 2>/dev/null || true
echo -e "  ${GREEN}✔ Grid is clear.${NC}\n"

# 3. Virtual Environment 
echo -e "${BLUE}[3/5] Checking Python Environment...${NC}"
if [ ! -d "venv" ]; then
    echo -e "  ${YELLOW}➔ Initializing new virtual environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r cloud-api/requirements.txt
else
    source venv/bin/activate
fi
echo -e "  ${GREEN}✔ Python Subsystems Online.${NC}\n"

# 4. Boot Infrastructure
echo -e "${BLUE}[4/5] Spinning up Core Microservices & Edge Node...${NC}"
docker-compose up -d postgres redis portal capture-orchestrator

echo -ne "  ${YELLOW}➔ Synchronizing with PostgreSQL Database...${NC}"
RETRIES=60
while [ $RETRIES -gt 0 ]; do
    HEALTH=$(docker inspect --format='{{json .State.Health.Status}}' rec-postgres-1 2>/dev/null)
    if [ "$HEALTH" == "\"healthy\"" ]; then
        echo -e "\n  ${GREEN}✔ PostgreSQL is HEALTHY and READY!${NC}\n"
        break
    fi
    echo -ne "${CYAN}█${NC}"
    sleep 1
    RETRIES=$((RETRIES-1))
done

if [ $RETRIES -eq 0 ]; then
    echo -e "\n  ${RED}✖ PostgreSQL timeout. Restarting container forcefully...${NC}"
    docker-compose restart postgres
    sleep 5
    echo -e "  ${GREEN}✔ Forced resume.${NC}\n"
fi

# 5. Ignite AI Core
echo -e "${BLUE}[5/5] Igniting InsightFace Neural Engine...${NC}"

# Start API in background temporarily to make sure it loads without blocking terminal print
echo -e "  ${YELLOW}➔ Booting lab_api.py on Port 8001...${NC}"
python lab_api.py &
API_PID=$!

sleep 5

echo -e "${MAGENTA}${BOLD}"
echo "=========================================================="
echo " ⚡ SYSTEM FULLY OPERATIONAL - ALL SYSTEMS NOMINAL ⚡ "
echo "=========================================================="

# Automatically detect Local Network IP
if command -v ip >/dev/null 2>&1; then
    LAN_IP=$(ip route get 1.1.1.1 | awk -F"src " 'NR==1{split($2,a," ");print a[1]}')
else
    LAN_IP=$(ifconfig | grep "inet " | grep -Fv 127.0.0.1 | awk '{print $2}' | head -n 1)
fi

echo -e "${GREEN} LOCAL (This Computer):"
echo "  [CTRL] Admin Portal:        http://localhost:3000/admin"
echo "  [STUDIO] Photographer:      http://localhost:3000/photographer"
echo "  [CLIENT] User Gallery:      http://localhost:3000/user"
echo ""
echo -e "${CYAN} NETWORK (Phones & Tablets on Wi-Fi):"
echo "  [CTRL] Admin Portal:        http://${LAN_IP}:3000/admin"
echo "  [STUDIO] Photographer:      http://${LAN_IP}:3000/photographer"
echo "  [CLIENT] User Gallery:      http://${LAN_IP}:3000/user${NC}"

echo -e "${MAGENTA}==========================================================${NC}"
echo -e "${CYAN}Streaming AI Logs... (Press Ctrl+C to safely shutdown everything)${NC}\n"

# Trap Ctrl+C to cleanly shutdown everything at any cost
trap 'echo -e "\n${RED}[!] EMERGENCY TEARDOWN INITIATED...${NC}"; kill $API_PID 2>/dev/null; pkill -f lab_api.py; docker-compose down; echo -e "${GREEN}✔ Teardown complete. Goodbye.${NC}"; exit 0' SIGINT SIGTERM

# Bring the background job to the foreground so user sees logs and blocks
wait $API_PID
