#!/bin/bash

set -e

if [ "$EUID" -ne 0 ]; then
    echo "❌ Перезапустите скрипт с правами root (sudo)"
    exit 1
fi

REPO_URL="https://github.com/Not-a-dude/Komaru-FunBox.git"
INSTALL_DIR="/opt/Komaru-FunBox"

echo -n "✍️ Введите имя ветки (например, main или test): "
read branch_name

# Проверка ветки
if ! git ls-remote --heads "$REPO_URL" "$branch_name" &> /dev/null; then
    echo "❌ Ветка '$branch_name' не найдена!"
    exit 1
fi

echo "🚀 Начинаем Docker-деплой Komaru FunBox..."

# 1. Установка Docker, если его нет
if ! command -v docker &> /dev/null; then
    echo "📦 Устанавливаю Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
fi

# 2. Подготовка папки
echo "📦 Клонирую репозиторий в $INSTALL_DIR..."
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
fi
git clone -b "$branch_name" "$REPO_URL" "$INSTALL_DIR"
cd "$INSTALL_DIR"

git config --global --add safe.directory "$INSTALL_DIR"

# 4. Генерация .env
DB_PASSWORD=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 16)
if [ -f "env_example" ]; then
    cp env_example .env
    sed -i "s/your_db_password/$DB_PASSWORD/g" .env
    sed -i "s/your_db_host/db/g" .env
    echo "✅ .env создан. Сгенерирован пароль БД: $DB_PASSWORD"
else
    echo "⚠️ env_example не найден, создайте .env вручную."
fi

echo "⚙️ Открываю .env для настройки API ключей..."
sleep 2
nano .env

# 5. Запуск
echo "🏗️ Собираю и запускаю контейнеры..."
docker compose up -d --build

echo "✅ Установка завершена!"
echo "📝 Логи бота: docker compose logs -f bot"
echo "🔄 Бот будет автоматически перезапускаться при сбоях."