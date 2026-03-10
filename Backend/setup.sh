#!/bin/bash
# setup.sh — One-shot local setup for RepoMind backend

set -e   # exit on any error

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== RepoMind Backend Setup ===${NC}\n"

# ── 1. Python version check ───────────────────────────────────────────────────
echo -e "${YELLOW}[1/6] Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
required="3.11"
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"; then
    echo -e "  ✅ Python $python_version OK"
else
    echo -e "  ${RED}❌ Python 3.11+ required (got $python_version)${NC}"
    exit 1
fi

# ── 2. Virtual environment ────────────────────────────────────────────────────
echo -e "\n${YELLOW}[2/6] Creating virtual environment...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "  ✅ Created .venv"
else
    echo -e "  ✅ .venv already exists"
fi

source .venv/bin/activate

# ── 3. Install dependencies ───────────────────────────────────────────────────
echo -e "\n${YELLOW}[3/6] Installing Python dependencies...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "  ✅ Dependencies installed"

# ── 4. .env file ─────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[4/6] Checking .env file...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "  ✅ Created .env from template"
    echo -e "  ${YELLOW}⚠️  Edit .env and add your GITHUB_TOKEN before running!${NC}"
else
    echo -e "  ✅ .env already exists"
fi

# ── 5. Docker services (Qdrant) ───────────────────────────────────────────────
echo -e "\n${YELLOW}[5/6] Checking Docker services...${NC}"
if command -v docker &> /dev/null; then
    if ! docker ps | grep -q qdrant; then
        echo -e "  Starting Qdrant..."
        docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest
        echo -e "  ✅ Qdrant started on http://localhost:6333"
    else
        echo -e "  ✅ Qdrant already running"
    fi
else
    echo -e "  ${YELLOW}⚠️  Docker not found. Start Qdrant manually:${NC}"
    echo -e "     docker run -p 6333:6333 qdrant/qdrant"
fi

# ── 6. Ollama check ───────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[6/6] Checking Ollama...${NC}"
if command -v ollama &> /dev/null; then
    echo -e "  ✅ Ollama installed"
    if ollama list | grep -q "codellama"; then
        echo -e "  ✅ codellama model ready"
    else
        echo -e "  Pulling codellama (this takes a few minutes)..."
        ollama pull codellama
        echo -e "  ✅ codellama ready"
    fi
else
    echo -e "  ${YELLOW}⚠️  Ollama not found. Install from: https://ollama.ai${NC}"
    echo -e "     Then run: ollama pull codellama"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}=== Setup Complete! ===${NC}"
echo -e "\nTo start the backend:"
echo -e "  ${YELLOW}source .venv/bin/activate${NC}"
echo -e "  ${YELLOW}python main.py${NC}"
echo -e "\nAPI will be available at: ${GREEN}http://localhost:8000${NC}"
echo -e "API docs at:              ${GREEN}http://localhost:8000/docs${NC}\n"
