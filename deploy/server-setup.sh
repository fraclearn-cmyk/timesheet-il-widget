#!/bin/bash
# Server Setup Script for Timesheet IL
# Run this on your fresh Ubuntu 22.04 server

set -e

echo "=========================================="
echo "  Timesheet IL - Server Setup"
echo "  Ubuntu 22.04 LTS"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use: sudo bash server-setup.sh)"
    exit 1
fi

# Update system
echo "Step 1: Updating system..."
apt update
apt upgrade -y
echo "✓ System updated"
echo ""

# Install basic utilities
echo "Step 2: Installing basic utilities..."
apt install -y curl wget git nano htop ufw
echo "✓ Utilities installed"
echo ""

# Install Docker
echo "Step 3: Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    echo "✓ Docker installed"
else
    echo "✓ Docker already installed"
fi
docker --version
echo ""

# Install Docker Compose
echo "Step 4: Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    apt install -y docker-compose
    echo "✓ Docker Compose installed"
else
    echo "✓ Docker Compose already installed"
fi
docker-compose --version
echo ""

# Install Nginx
echo "Step 5: Installing Nginx..."
if ! command -v nginx &> /dev/null; then
    apt install -y nginx
    systemctl start nginx
    systemctl enable nginx
    echo "✓ Nginx installed and started"
else
    echo "✓ Nginx already installed"
fi
nginx -v
echo ""

# Install Certbot
echo "Step 6: Installing Certbot..."
if ! command -v certbot &> /dev/null; then
    apt install -y certbot python3-certbot-nginx
    echo "✓ Certbot installed"
else
    echo "✓ Certbot already installed"
fi
certbot --version
echo ""

# Setup Firewall
echo "Step 7: Configuring Firewall..."
ufw --force enable
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
echo "✓ Firewall configured"
ufw status
echo ""

# Create application directory
echo "Step 8: Creating application directory..."
mkdir -p /opt/timesheet
mkdir -p /var/log/timesheet
echo "✓ Directories created"
echo ""

# Create log rotation config
echo "Step 9: Configuring log rotation..."
cat > /etc/logrotate.d/timesheet << 'EOF'
/var/log/timesheet/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
}
EOF
echo "✓ Log rotation configured"
echo ""

echo "=========================================="
echo "  SERVER SETUP COMPLETE!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Copy your application code to /opt/timesheet"
echo "2. Create .env file in /opt/timesheet"
echo "3. Configure Nginx for your domain"
echo "4. Get SSL certificate with certbot"
echo "5. Start application with docker-compose"
echo ""
echo "Server IP: $(curl -s ifconfig.me)"
echo ""
echo "Read full guide: PRODUCTION_DEPLOYMENT.md"
echo ""
