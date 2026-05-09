#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Prospecting Service - Quickstart${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found${NC}"

# Create or activate virtual environment
echo -e "\n${YELLOW}Setting up Python virtual environment...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

source .venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Install requirements
echo -e "\n${YELLOW}Installing dependencies...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -q -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${RED}✗ requirements.txt not found${NC}"
    exit 1
fi

# Check if MongoDB is accessible
echo -e "\n${YELLOW}Checking MongoDB connectivity...${NC}"
MONGODB_URI="${MONGODB_URI:-mongodb://localhost:27017}"
if command -v mongosh &> /dev/null; then
    if mongosh "$MONGODB_URI" --eval "db.version()" &> /dev/null; then
        echo -e "${GREEN}✓ MongoDB is accessible at $MONGODB_URI${NC}"
    else
        echo -e "${RED}✗ MongoDB is not accessible at $MONGODB_URI${NC}"
        echo -e "${YELLOW}  Please ensure MongoDB is running or set MONGODB_URI environment variable${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ mongosh not found - skipping MongoDB connectivity check${NC}"
    echo -e "${YELLOW}  Make sure MongoDB is running at: $MONGODB_URI${NC}"
fi

# Check if RabbitMQ is accessible
echo -e "\n${YELLOW}Checking RabbitMQ connectivity...${NC}"
RABBITMQ_URL="${RABBITMQ_URL:-amqp://guest:guest@localhost:5672/%2F}"
if python3 -c "import pika; pika.BlockingConnection(pika.URLParameters('$RABBITMQ_URL'))" 2>/dev/null; then
    echo -e "${GREEN}✓ RabbitMQ is accessible at $RABBITMQ_URL${NC}"
else
    echo -e "${RED}✗ RabbitMQ is not accessible at $RABBITMQ_URL${NC}"
    echo -e "${YELLOW}  Start RabbitMQ with:${NC}"
    echo -e "${YELLOW}    cd src/local_infrastructure/rabbit_mq${NC}"
    echo -e "${YELLOW}    cp .env.example .env${NC}"
    echo -e "${YELLOW}    docker compose up -d${NC}"
    exit 1
fi

# Set environment variables if not already set
echo -e "\n${YELLOW}Configuring environment variables...${NC}"
export RABBITMQ_URL="${RABBITMQ_URL:-amqp://guest:guest@localhost:5672/%2F}"
export RABBITMQ_EXCHANGE="${RABBITMQ_EXCHANGE:-email_outreach.events}"
export RABBITMQ_PREFETCH="${RABBITMQ_PREFETCH:-10}"
export MONGODB_URI="${MONGODB_URI:-mongodb://localhost:27017}"
export MONGODB_DB="${MONGODB_DB:-email_outreach}"
export DEFAULT_MIN_ICP_SCORE="${DEFAULT_MIN_ICP_SCORE:-0.0}"

echo -e "${GREEN}✓ Environment variables set:${NC}"
echo "  RABBITMQ_URL=$RABBITMQ_URL"
echo "  RABBITMQ_EXCHANGE=$RABBITMQ_EXCHANGE"
echo "  MONGODB_URI=$MONGODB_URI"
echo "  MONGODB_DB=$MONGODB_DB"

# Run the service
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Starting Prospecting Service...${NC}"
echo -e "${GREEN}========================================${NC}\n"

python -m app.main
