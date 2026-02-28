#!/bin/bash
set -e

git config --global --add safe.directory /opt/Komaru-FunBox

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Wait for database to be ready
echo -e "${BLUE}⏳ Waiting for database to be ready...${NC}"
max_retries=30
count=0

while ! pg_isready -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" 2>/dev/null; do
    count=$((count + 1))
    if [ $count -ge $max_retries ]; then
        echo -e "${RED}❌ Database connection failed after $max_retries attempts${NC}"
        exit 1
    fi
    echo -e "${YELLOW}⏳ Database not ready, retrying... ($count/$max_retries)${NC}"
    sleep 1
done

echo -e "${GREEN}✅ Database is ready!${NC}"

# Check for auto-update on startup
if [ "${AUTO_UPDATE:-false}" = "true" ]; then
    echo -e "${BLUE}🔄 AUTO_UPDATE enabled, checking for updates...${NC}"
    if cd /opt/Komaru-FunBox && git fetch --quiet origin; then
        CURRENT=$(git rev-parse HEAD)
        LATEST=$(git rev-parse origin/$(git rev-parse --abbrev-ref HEAD) 2>/dev/null || echo "$CURRENT")
        
        if [ "$CURRENT" != "$LATEST" ]; then
            echo -e "${YELLOW}📦 Updates available, pulling changes...${NC}"
            git pull --quiet origin $(git rev-parse --abbrev-ref HEAD) || true
        else
            echo -e "${GREEN}✅ Already up to date${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️ Failed to check for updates, continuing anyway${NC}"
    fi
fi

# Start the bot
echo -e "${GREEN}🤖 Starting bot...${NC}"
exec python -u -m bot
