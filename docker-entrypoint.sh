#!/bin/bash
set -e

TARGET_DIR="${APP_DIR:-/app}"

git config --global --add safe.directory "$TARGET_DIR"

# Цветовые коды для терминала
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # Без цвета

# Ожидаем БД
echo -e "${BLUE}⏳ Ожидаем готовности базы данных...${NC}"
max_retries=30
count=0

while ! pg_isready -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" 2>/dev/null; do
    count=$((count + 1))
    if [ $count -ge $max_retries ]; then
        echo -e "${RED}❌ Подключение к базе данных не удалось после $max_retries попыток${NC}"
        exit 1
    fi
    echo -e "${YELLOW}⏳ База данных не готова, повторная попытка... ($count/$max_retries)${NC}"
    sleep 1
done

    echo -e "${GREEN}✅ База данных готова!${NC}"

# Проверяем наличие обновлений, если AUTO_UPDATE включено
if [ "${AUTO_UPDATE:-false}" = "true" ]; then
    echo -e "${BLUE}🔄 AUTO_UPDATE включено, проверяем обновления...${NC}"
    if cd "$TARGET_DIR" && git fetch --quiet origin; then
        CURRENT=$(git rev-parse HEAD)
        LATEST=$(git rev-parse origin/$(git rev-parse --abbrev-ref HEAD) 2>/dev/null || echo "$CURRENT")
        
        if [ "$CURRENT" != "$LATEST" ]; then
            echo -e "${YELLOW}📦 Обновления доступны, обновляем...${NC}"
            git pull --quiet origin $(git rev-parse --abbrev-ref HEAD) || true
        else
            echo -e "${GREEN}✅ Уже обновлено${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️ Не удалось проверить обновления, продолжаем...${NC}"
    fi
fi

# CПроверяем и устанавливаем зависимости
if [ -f "requirements.txt" ]; then
    echo -e "${BLUE}📦 Проверяем/устанавливаем зависимости...${NC}"
    pip install --no-cache-dir -r requirements.txt --quiet
fi

# Запускаем бота
echo -e "${GREEN}🤖 Запускаем бота...${NC}"
exec python -u -m bot
