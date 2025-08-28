#!/bin/bash
set -e

# Configuration
EC2_HOST="3.237.242.91" # Will be populated after terraform apply
SSH_KEY="salman-dev.pem"
REPO_URL="https://github.com/main-salman/greenspace-mei.git"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Updating Greenspace app on EC2...${NC}"

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

# Update the application
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ec2-user@"$EC2_HOST" << 'EOF'
set -e

echo "🔄 Updating Greenspace application..."

cd /home/ec2-user/greenspace-mei

# Pull latest changes
echo "📥 Pulling latest code from repository..."
git pull origin main

# Update Python dependencies
echo "📦 Updating Python dependencies..."
source local_venv/bin/activate
pip install --upgrade pip
pip install -r local_app/requirements.txt

# Rebuild Next.js app
echo "🏗️ Building Next.js application..."
cd greenspace-app
npm install
npm run build
npm run export
cd ..

# Restart the service
echo "🔄 Restarting Greenspace service..."
sudo systemctl restart greenspace

# Check service status
echo "✅ Checking service status..."
sudo systemctl status greenspace --no-pager -l

echo "🎉 Update completed successfully!"
EOF

echo -e "${GREEN}✅ Greenspace app updated successfully!${NC}"
echo -e "${GREEN}🌐 App should be available at: https://greenspace.qolimpact.click${NC}"
