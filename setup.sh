#!/bin/bash

set -e

if [ "$EUID" -ne 0 ]; then
    echo "❌ Перезапустите этот скрипт с правами root"
    exit 1
fi

SERVICE_NAME="komaru-funbox"
if [ "$branch_name" != "release" ]; then
    SERVICE_NAME="${SERVICE_NAME}_$branch_name"
fi
USER_NAME="komaru"
GROUP_NAME="komaru-group"
INSTALL_DIR="/home/${USER_NAME}/komaru-funbox"
REPO_URL="https://github.com/Komaru-dude/Komaru-FunBox.git"
echo -n "✍️ Введите имя гитхаб ветки: "
read branch_name

git ls-remote --heads "$REPO_URL" "$branch_name" &> /dev/null

if [ $? -ne 0 ]; then
    echo "Ветка '$branch_name' не найдена в репозитории $REPO_URL."
    exit 1
fi

if [ "$branch_name" != "release" ]; then
    INSTALL_DIR="${INSTALL_DIR}_$branch_name"
fi

echo "🚀 Начинаем установку Komaru FunBox..."

echo "🔄 Обновляем пакеты и устанавливаем зависимости..."
apt update
apt install -y python3-venv git build-essential autoconf automake libtool pkg-config yt-dlp ffmpeg postgresql
snap install gifski

if ! id -u ${USER_NAME} >/dev/null 2>&1; then
    echo "👤 Создаём системного пользователя: ${USER_NAME}"
    useradd --system --create-home --shell /bin/false ${USER_NAME}
fi

if ! grep -q "^${GROUP_NAME}:" /etc/group; then
    echo "👥 Создаём группу: ${GROUP_NAME}"
    groupadd ${GROUP_NAME}
    usermod -aG ${GROUP_NAME} ${USER_NAME}
fi

echo "📦 Клонируем репозиторий..."
if [ -d "${INSTALL_DIR}" ]; then
    echo "❌ Удаляем старый репозиторий..."
    rm -rf "${INSTALL_DIR}"
fi
sudo -u ${USER_NAME} git clone -b $branch_name ${REPO_URL} "${INSTALL_DIR}"

echo "🌪 Инициализируем PostgreSQL бд"

DB_NAME="funbox_db"
DB_USER="komaru"
DB_PASSWORD=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 16)

if [ "$branch_name" != "release" ]; then
    DB_NAME="${branch_name}_${DB_NAME}"
fi

echo "Сгенерированный пароль для: $DB_USER: $DB_PASSWORD"  > /home/${USER_NAME}/db_credentials.txt
chown ${USER_NAME}:${GROUP_NAME} /home/${USER_NAME}/db_credentials.txt

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
fi

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
fi

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

echo "🐍 Создаём виртуальное окружение python..."
sudo -u ${USER_NAME} python3 -m venv "${INSTALL_DIR}/venv"

echo "📦 Устанавливаем зависимости python..."
sudo -u ${USER_NAME} "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

ENV_FILE="${INSTALL_DIR}/.env"
ENV_EXAMPLE="${INSTALL_DIR}/env_example"

echo "🛠 Генерируем .env из шаблона..."

if [ ! -f "$ENV_EXAMPLE" ]; then
    echo "❌ env_example не был найден!"
    exit 1
fi

sudo -u ${USER_NAME} cp "$ENV_EXAMPLE" "$ENV_FILE"
sudo -u ${USER_NAME} sed -i "s/your_db_name/$DB_NAME/g" "$ENV_FILE"
sudo -u ${USER_NAME} sed -i "s/your_db_user/$DB_USER/g" "$ENV_FILE"
sudo -u ${USER_NAME} sed -i "s/your_db_password/$DB_PASSWORD/g" "$ENV_FILE"
sudo -u ${USER_NAME} sed -i "s/your_db_host/localhost/g" "$ENV_FILE"
sudo -u ${USER_NAME} sed -i "s/your_db_port/5432/g" "$ENV_FILE"

chown ${USER_NAME}:${GROUP_NAME} "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

echo "✅ .env файл создан. Измените оставшиеся парсметры..."
sudo -u ${USER_NAME} nano "${ENV_FILE}"

echo "⚙ Создаём systemd сервис..."
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
if [ "$branch_name" != "release" ]; then
    SERVICE_FILE="${SERVICE_FILE}_$branch_name"
fi
cat > ${SERVICE_FILE} << EOL
[Unit]
Description=Komaru FunBox bot
After=network.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStartPre=/bin/chmod +x ${INSTALL_DIR}/force-pull.sh
ExecStartPre=/bin/bash ${INSTALL_DIR}/force-pull.sh
ExecStart=${INSTALL_DIR}/venv/bin/python -u -m bot
KillMode=process
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
User=${USER_NAME}
Group=${GROUP_NAME}
Environment=USER=%n
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games"
Environment="HOME=/home/${USER_NAME}"
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOL

echo "🔒 Настраиваем привлегии..."
chown -R ${USER_NAME}:${GROUP_NAME} ${INSTALL_DIR}
chmod 700 ${INSTALL_DIR}
chmod +x ${INSTALL_DIR}/force-pull.sh
echo "komaru ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart komaru-funbox.service" | visudo -f /etc/sudoers.d/komaru-funbox
usermod -aG systemd-journal ${USER_NAME}
chmod 600 db_credentials.txt

echo "🔄 Перезапускаем systemd и включаем сервис..."
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl start ${SERVICE_NAME}

echo "✅ Установка прошла успешно!"
echo " "
echo "Инструкция по использованию:"
echo "  Запустить сервис:    systemctl start ${SERVICE_NAME}"
echo "  Остановить сервис:   systemctl stop ${SERVICE_NAME}"
echo "  Перезапустить сервис: systemctl restart ${SERVICE_NAME}"
echo "  Проверить статус:    systemctl status ${SERVICE_NAME}"
echo "  Просмотреть логи:    journalctl -u ${SERVICE_NAME} -f"
echo " "
echo "Редактировать конфигурацию: nano ${INSTALL_DIR}/.env"
echo "Не забудьте перезапустить сервис при изменении конфигурации!"