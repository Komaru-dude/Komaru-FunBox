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
apt-get update
apt-get install -y python3-venv git build-essential autoconf automake libtool pkg-config yt-dlp ffmpeg postgresql
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

echo "🐍 Creating Python virtual environment..."
sudo -u ${USER_NAME} python3 -m venv "${INSTALL_DIR}/venv"

echo "📦 Installing Python dependencies..."
sudo -u ${USER_NAME} "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

ENV_FILE="${INSTALL_DIR}/.env"
if [ ! -f "${ENV_FILE}" ]; then
    echo "🛠 Setting up .env file..."
    sudo -u ${USER_NAME} mv ${INSTALL_DIR}/env_example ${ENV_FILE}
    echo "⚠️ IMPORTANT: You will need to configure the .env file. Please review and set it up properly."
    echo "Press any key to continue..."
    read -n 1 -s
    sudo -u ${USER_NAME} nano ${ENV_FILE}
    echo "⚠️⚠️⚠️ NOTE: If you haven't set up .env correctly, you'll have to do it yourself. ⚠️⚠️⚠️"
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