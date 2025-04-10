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

echo "🚀 Starting Komaru FunBox installation..."

echo "🔄 Updating packages and installing dependencies..."
apt-get update
apt-get install -y python3-venv git build-essential autoconf automake libtool pkg-config

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
sudo -u ${USER_NAME} git config --global --add safe.directory /home/${USER_NAME}/komaru-funbox
if [ -d "${INSTALL_DIR}/.git" ]; then
    git -C "${INSTALL_DIR}" pull
else
    sudo -u ${USER_NAME} git clone ${REPO_URL} "${INSTALL_DIR}"
fi

echo "🐍 Creating Python virtual environment..."
sudo -u ${USER_NAME} python3 -m venv "${INSTALL_DIR}/venv"

echo "📦 Installing Python dependencies..."
sudo -u ${USER_NAME} "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

ENV_FILE="${INSTALL_DIR}/.env"
if [ ! -f "${ENV_FILE}" ]; then
    echo "🛠 Creating .env file template..."
    sudo -u ${USER_NAME} touch "${ENV_FILE}"
    echo "⚠️⚠️⚠️ NOTE: You must configure .env yourself using the example in env_example ⚠️⚠️⚠️"
fi

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
ExecStartPre=/usr/bin/git -C ${INSTALL_DIR} pull
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