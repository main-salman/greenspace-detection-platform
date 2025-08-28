#!/bin/bash

# Configuration
EC2_HOST="3.237.242.91" # Populated by terraform apply
SSH_KEY="salman-dev.pem"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Greenspace App Troubleshooting${NC}"
echo -e "${BLUE}================================${NC}"

# Check if EC2_HOST is set
if [ -z "$EC2_HOST" ]; then
    echo -e "${RED}❌ EC2_HOST not set. Please run 'terraform output ec2_public_ip' and update this script.${NC}"
    exit 1
fi

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}❌ SSH key $SSH_KEY not found. Please ensure it exists in the current directory.${NC}"
    exit 1
fi

echo -e "${YELLOW}📡 Connecting to EC2 instance: $EC2_HOST${NC}"

# Run troubleshooting commands
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ec2-user@"$EC2_HOST" << 'EOF'
echo "🔍 Greenspace App Troubleshooting Report"
echo "========================================"

echo ""
echo "📊 System Status:"
echo "----------------"
echo "Uptime: $(uptime)"
echo "Disk Usage: $(df -h / | tail -1)"
echo "Memory Usage: $(free -h | grep Mem)"

echo ""
echo "🔧 Service Status:"
echo "-----------------"
sudo systemctl status greenspace --no-pager -l || echo "❌ Greenspace service not found"

echo ""
echo "🌐 Nginx Status:"
echo "---------------"
sudo systemctl status nginx --no-pager -l || echo "❌ Nginx service not found"

echo ""
echo "🔍 Process Status:"
echo "-----------------"
echo "Python processes:"
ps aux | grep python | grep -v grep || echo "No Python processes found"

echo ""
echo "📝 Recent Logs:"
echo "--------------"
echo "Greenspace service logs (last 20 lines):"
sudo journalctl -u greenspace -n 20 --no-pager || echo "No greenspace service logs"

echo ""
echo "Application logs (last 20 lines):"
if [ -f "/home/ec2-user/greenspace-mei/greenspace_app.log" ]; then
    tail -20 /home/ec2-user/greenspace-mei/greenspace_app.log
else
    echo "No application log file found"
fi

echo ""
echo "Nginx error logs (last 10 lines):"
if [ -f "/var/log/nginx/error.log" ]; then
    sudo tail -10 /var/log/nginx/error.log
else
    echo "No nginx error log found"
fi

echo ""
echo "🔗 Network Status:"
echo "-----------------"
echo "Listening ports:"
sudo netstat -tlnp | grep -E ':(80|443|8000)' || echo "No web services listening"

echo ""
echo "🗂️ File System:"
echo "---------------"
echo "Greenspace directory:"
ls -la /home/ec2-user/greenspace-mei/ 2>/dev/null || echo "Greenspace directory not found"

echo ""
echo "Virtual environment:"
ls -la /home/ec2-user/greenspace-mei/local_venv/ 2>/dev/null || echo "Virtual environment not found"

echo ""
echo "🔐 SSL Certificate:"
echo "------------------"
if [ -f "/etc/letsencrypt/live/greenspace.qolimpact.click/fullchain.pem" ]; then
    echo "✅ SSL certificate exists"
    sudo openssl x509 -in /etc/letsencrypt/live/greenspace.qolimpact.click/fullchain.pem -text -noout | grep -A2 "Validity"
else
    echo "❌ SSL certificate not found"
fi

echo ""
echo "========================================"
echo "🏁 Troubleshooting report completed"
EOF

echo -e "${GREEN}✅ Troubleshooting report completed${NC}"
