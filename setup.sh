#!/usr/bin/env bash
# One-command setup for AI Orchestration project

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  AI Orchestration - Complete Setup                    ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════╝${NC}"
echo

# 1. Check Python version
echo -e "${YELLOW}📋 Checking prerequisites...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}❌ Python $REQUIRED_VERSION+ required (found $PYTHON_VERSION)${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"

# 2. Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo -e "\n${YELLOW}🐍 Creating virtual environment...${NC}"
    python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
fi

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Install dependencies
echo -e "\n${YELLOW}📦 Installing dependencies...${NC}"
pip install -q --upgrade pip
pip install -q launchdarkly-ai-server launchdarkly-server-sdk python-dotenv arxiv PyPDF2 requests
pip install -q strands-sdk langgraph autogen-agentchat swarm anthropic openai
echo -e "${GREEN}✓ All dependencies installed${NC}"

# 5. Check environment variables
echo -e "\n${YELLOW}🔑 Checking environment variables...${NC}"

ENV_FILE=".env"
MISSING_VARS=()

# Required variables
REQUIRED_VARS=(
    "LD_SDK_KEY"
    "LD_API_KEY"
    "ANTHROPIC_API_KEY"
    "OPENAI_API_KEY"
)

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ .env file not found${NC}"
    echo -e "${YELLOW}Please create .env with your API keys${NC}"
    exit 1
fi

# Source the .env file
set -a
source .env
set +a

# Check required variables
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    else
        # Mask the key for display
        masked=$(echo "${!var}" | sed 's/\(.....\).*/\1***/')
        echo -e "${GREEN}✓ $var = $masked${NC}"
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo -e "\n${RED}❌ Missing required environment variables:${NC}"
    for var in "${MISSING_VARS[@]}"; do
        echo -e "${RED}  - $var${NC}"
    done
    exit 1
fi

echo -e "\n${GREEN}✅ Setup complete! Ready to run orchestrators.${NC}"
echo -e "\nNext steps:"
echo -e "  1. Download papers: ${YELLOW}python scripts/download_papers.py${NC}"
echo -e "  2. Bootstrap configs: ${YELLOW}python scripts/launchdarkly/bootstrap.py${NC}"
echo -e "  3. Run orchestrator: ${YELLOW}python orchestrators/langgraph/run_gap_analysis.py --papers-json data/combined_ai_agent_papers.json${NC}"
