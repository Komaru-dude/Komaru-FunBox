#!/bin/bash

set -e

if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run this script as root"
    exit 1
fi

SERVICE_NAME="komaru-funbox"
USER_NAME="komaru"
GROUP_NAME="komaru-group"
INSTALL_DIR="/home/${USER_NAME}/komaru-funbox"
REPO_URL="https://github.com/Komaru-dude/Komaru-FunBox.git"
echo -n "✍️ Enter github branch name: "
read branch_name

git ls-remote --heads "$REPO_URL" "$branch_name" &> /dev/null

if [ $? -ne 0 ]; then
    echo "Branch '$branch_name' not found on repo $REPO_URL."
    exit 1
fi

echo "🚀 Starting Komaru FunBox installation..."

echo "🔄 Updating packages and installing dependencies..."
apt update
apt install -y python3-venv git build-essential autoconf automake libtool pkg-config yt-dlp ffmpeg postgresql
snap install gifski

if ! id -u ${USER_NAME} >/dev/null 2>&1; then
    echo "👤 Creating system user: ${USER_NAME}"
    useradd --system --create-home --shell /bin/false ${USER_NAME}
fi

if ! grep -q "^${GROUP_NAME}:" /etc/group; then
    echo "👥 Creating group: ${GROUP_NAME}"
    groupadd ${GROUP_NAME}
    usermod -aG ${GROUP_NAME} ${USER_NAME}
fi

echo "📦 Cloning/updating repository..."
if [ -d "${INSTALL_DIR}" ]; then
    echo "❌ Removing old repository..."
    rm -rf "${INSTALL_DIR}"
fi
sudo -u ${USER_NAME} git clone -b $branch_name ${REPO_URL} "${INSTALL_DIR}"
if [ "$branch_name" = "test" ]; then
    touch test
else
    rm -f test  # на всякий случай удаляем, если был
fi

echo "🌪 Initialize PostgreSQL db"

DB_NAME="funbox_db"
DB_USER="komaru"
DB_PASSWORD=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 16)

# Сохраняем пароль в файл
echo "Generated password for $DB_USER: $DB_PASSWORD"  > /home/${USER_NAME}/db_credentials.txt
chown ${USER_NAME}:${GROUP_NAME} /home/${USER_NAME}/db_credentials.txt

# Проверка и создание пользователя
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
fi

# Проверка и создание базы
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
fi

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

echo "🐍 Creating Python virtual environment..."
sudo -u ${USER_NAME} python3 -m venv "${INSTALL_DIR}/venv"

echo "📦 Installing Python dependencies..."
sudo -u ${USER_NAME} "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

ENV_FILE="${INSTALL_DIR}/.env"
echo "🛠 Generating .env file..."

cat > "${ENV_FILE}" <<EOF
# Database
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=localhost
DB_PORT=5432

# Bot settings (you should review and edit as needed)
BOT_TOKEN=
OWNER_ID=
EOF

chown ${USER_NAME}:${GROUP_NAME} "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

echo "✅ .env file created at ${ENV_FILE}."
echo "⚠️ Please edit it to add missing values like BOT_TOKEN and OWNER_ID."
read -p "Press any key to open nano... " -n 1 -s
sudo -u ${USER_NAME} nano ${ENV_FILE}

echo "⚙ Creating systemd service..."
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
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
ExecStart=${INSTALL_DIR}/venv/bin/python -m bot
KillMode=process
Restart=always
RestartSec=10
User=${USER_NAME}
Group=${GROUP_NAME}
Environment=USER=%n

[Install]
WantedBy=multi-user.target
EOL

echo "🔒 Setting permissions..."
chown -R ${USER_NAME}:${GROUP_NAME} ${INSTALL_DIR}
chmod 700 ${INSTALL_DIR}
chmod +x ${INSTALL_DIR}/force-pull.sh
echo "komaru ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart komaru-funbox.service" | visudo -f /etc/sudoers.d/komaru-funbox
chmod 600 db_credentials.txt

echo "🔄 Reloading systemd and enabling service..."
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl start ${SERVICE_NAME}

echo "✅ Installation completed successfully!"
echo " "
echo "Usage instructions:"
echo "  Start service:    systemctl start ${SERVICE_NAME}"
echo "  Stop service:     systemctl stop ${SERVICE_NAME}"
echo "  Restart service:  systemctl restart ${SERVICE_NAME}"
echo "  Check status:     systemctl status ${SERVICE_NAME}"
echo "  View logs:        journalctl -u ${SERVICE_NAME} -f"
echo " "
echo "Edit your configuration: nano ${INSTALL_DIR}/.env"
echo "Remember to restart the service after configuration changes!"