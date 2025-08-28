#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Deploying Greenspace App to AWS${NC}"
echo -e "${BLUE}======================================${NC}"

# Check if AWS credentials are set
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo -e "${YELLOW}⚠️  AWS credentials not found in environment variables.${NC}"
    echo -e "${YELLOW}Loading from .env file...${NC}"
    
    if [ -f ".env" ]; then
        export $(grep -v '^#' .env | xargs)
        echo -e "${GREEN}✅ AWS credentials loaded from .env file${NC}"
    else
        echo -e "${RED}❌ .env file not found. Please create it with AWS credentials.${NC}"
        exit 1
    fi
fi

# Verify Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Terraform is not installed. Please install Terraform first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"

# Initialize Terraform
echo -e "${YELLOW}🔧 Initializing Terraform...${NC}"
terraform init

# Plan the deployment
echo -e "${YELLOW}📋 Planning Terraform deployment...${NC}"
terraform plan

# Ask for confirmation
echo -e "${YELLOW}❓ Do you want to proceed with the deployment? (y/N)${NC}"
read -r response
if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo -e "${RED}❌ Deployment cancelled.${NC}"
    exit 0
fi

# Apply the configuration
echo -e "${YELLOW}🚀 Applying Terraform configuration...${NC}"
terraform apply -auto-approve

# Get the public IP
EC2_PUBLIC_IP=$(terraform output -raw ec2_public_ip)
echo -e "${GREEN}✅ EC2 Instance created with IP: $EC2_PUBLIC_IP${NC}"

# Update the update_ec2.sh script with the actual IP
sed -i.bak "s/EC2_HOST=\"\"/EC2_HOST=\"$EC2_PUBLIC_IP\"/" update_ec2.sh
echo -e "${GREEN}✅ Updated update_ec2.sh with EC2 IP address${NC}"

echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${GREEN}📍 EC2 Instance IP: $EC2_PUBLIC_IP${NC}"
echo -e "${GREEN}🌐 App URL: https://greenspace.qolimpact.click${NC}"
echo -e "${YELLOW}⏳ Note: It may take 5-10 minutes for the app to be fully ready${NC}"
echo -e "${YELLOW}📝 SSH Command: ssh -i salman-dev.pem ec2-user@$EC2_PUBLIC_IP${NC}"
echo -e "${BLUE}======================================${NC}"
