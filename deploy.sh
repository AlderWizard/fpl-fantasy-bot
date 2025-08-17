#!/bin/bash

# FPL Fantasy Football Bot Deployment Script
# Deploy to Raspberry Pi

set -e

echo "🚀 Deploying FPL Fantasy Football Bot to Raspberry Pi..."

# Configuration
PI_USER="zacalderman"
PI_HOST="192.168.0.66"
PI_PATH="/home/zacalderman/fpl-fantasy-bot"
LOCAL_PATH="."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}📋 Deployment Configuration:${NC}"
echo "  Target: $PI_USER@$PI_HOST:$PI_PATH"
echo "  Source: $LOCAL_PATH"
echo ""

# Check if we can connect to Pi
echo -e "${YELLOW}🔍 Testing SSH connection...${NC}"
if ssh -o ConnectTimeout=5 $PI_USER@$PI_HOST "echo 'Connection successful'" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ SSH connection successful${NC}"
else
    echo -e "${RED}❌ Cannot connect to Raspberry Pi${NC}"
    echo "Please check:"
    echo "  - Pi is powered on and connected to network"
    echo "  - SSH is enabled on Pi"
    echo "  - Correct IP address: $PI_HOST"
    echo "  - Correct username: $PI_USER"
    exit 1
fi

# Create directory on Pi
echo -e "${YELLOW}📁 Creating directory on Pi...${NC}"
ssh $PI_USER@$PI_HOST "mkdir -p $PI_PATH"

# Copy files to Pi
echo -e "${YELLOW}📤 Copying files to Pi...${NC}"
rsync -avz --progress \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='*.db' \
    --exclude='*.log' \
    $LOCAL_PATH/ $PI_USER@$PI_HOST:$PI_PATH/

# Install dependencies on Pi
echo -e "${YELLOW}📦 Installing dependencies on Pi...${NC}"
ssh $PI_USER@$PI_HOST "cd $PI_PATH && pip3 install -r requirements.txt"

# Set up environment file
echo -e "${YELLOW}⚙️ Setting up environment...${NC}"
ssh $PI_USER@$PI_HOST "cd $PI_PATH && if [ ! -f .env ]; then cp .env.example .env; echo 'Created .env file - please edit with your bot token'; fi"

# Create systemd service
echo -e "${YELLOW}🔧 Creating systemd service...${NC}"
ssh $PI_USER@$PI_HOST "sudo tee /etc/systemd/system/fpl-bot.service > /dev/null << EOF
[Unit]
Description=FPL Fantasy Football Bot
After=network.target

[Service]
Type=simple
User=$PI_USER
WorkingDirectory=$PI_PATH
ExecStart=/usr/bin/python3 run_fpl_bot.py
Restart=always
RestartSec=10
Environment=PYTHONPATH=$PI_PATH

[Install]
WantedBy=multi-user.target
EOF"

# Reload systemd and enable service
echo -e "${YELLOW}🔄 Configuring systemd service...${NC}"
ssh $PI_USER@$PI_HOST "sudo systemctl daemon-reload"
ssh $PI_USER@$PI_HOST "sudo systemctl enable fpl-bot"

echo ""
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo ""
echo -e "${YELLOW}📋 Next steps:${NC}"
echo "1. SSH to Pi: ssh $PI_USER@$PI_HOST"
echo "2. Edit environment: cd $PI_PATH && nano .env"
echo "3. Add your bot token: FPL_TELEGRAM_BOT_TOKEN=your_token_here"
echo "4. Start the bot: sudo systemctl start fpl-bot"
echo "5. Check status: sudo systemctl status fpl-bot"
echo "6. View logs: journalctl -u fpl-bot -f"
echo ""
echo -e "${GREEN}Bot will be available at: $PI_HOST${NC}"
