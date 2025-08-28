#!/bin/bash
set -x

echo "[user_data] Greenspace app setup started at $(date)"

# System dependencies
sudo yum update -y
sudo yum install -y git nginx unzip curl

# Install Node.js via Amazon Linux Extras
sudo amazon-linux-extras install -y nodejs14
sudo yum install -y npm

# Install Python 3.8 (required for the application)
sudo amazon-linux-extras install python3.8 -y
sudo yum install -y python3.8-pip python3.8-devel

# Create symlinks for easier usage
sudo ln -sf /usr/bin/python3.8 /usr/local/bin/python3
sudo ln -sf /usr/bin/pip3.8 /usr/local/bin/pip3

# Install additional system packages for satellite processing
sudo yum install -y gcc gcc-c++ gdal gdal-devel proj proj-devel geos geos-devel

# AWS CLI v2
sudo yum remove -y awscli || true
cd /tmp
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -o awscliv2.zip
sudo ./aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli --update
rm -rf awscliv2.zip aws
cd ~

export PATH=$PATH:/usr/local/bin

echo "[user_data] AWS CLI version:"
aws --version

# All project setup as ec2-user in /home/ec2-user
cat > /home/ec2-user/ec2_setup.sh <<'EOF'
cd /home/ec2-user
export PATH=$PATH:/usr/local/bin

echo "[user_data] Cloning greenspace app repo..."
if [ ! -d "greenspace-detection-platform" ]; then
  git clone https://github.com/main-salman/greenspace-detection-platform.git
fi
cd greenspace-detection-platform

echo "[user_data] Setting up Next.js application..."
cd greenspace-app

echo "[user_data] Installing Node.js dependencies..."
npm install

echo "[user_data] Building Next.js application..."
npm run build

echo "[user_data] Setting up Python virtual environment..."
if [ ! -d venv ]; then
  python3.8 -m venv venv
fi

echo "[user_data] Installing Python requirements..."
source venv/bin/activate
pip install --upgrade pip
pip install -r python_scripts/requirements.txt

echo "[user_data] Starting Next.js application..."
nohup npm start > ../greenspace_app.log 2>&1 &

echo "[user_data] Next.js application started on port 3000"
cd ..
EOF

sudo chown ec2-user:ec2-user /home/ec2-user/ec2_setup.sh
sudo chmod +x /home/ec2-user/ec2_setup.sh
sudo -u ec2-user bash /home/ec2-user/ec2_setup.sh
sudo rm -f /home/ec2-user/ec2_setup.sh

# --- HTTPS/NGINX/LETSENCRYPT SETUP ---
APP_DOMAIN="${APP_DOMAIN}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL}"

echo "[user_data] Installing and configuring Nginx and Certbot..."
sudo amazon-linux-extras install -y nginx1 epel
sudo yum install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
sudo yum install -y certbot

# Wait for network connectivity before proceeding
echo "[user_data] Checking network connectivity..."
for i in {1..10}; do
  curl -I https://github.com && break
  echo "[user_data] Network not ready, retrying in 5s... $i/10"
  sleep 5
done

# Start nginx and wait for it to be active
echo "[user_data] Starting nginx..."
sudo systemctl start nginx
for i in {1..10}; do
  sudo systemctl is-active --quiet nginx && break
  echo "[user_data] Waiting for nginx to become active... $i/10"
  sleep 2
done

# Write HTTP config
echo "[user_data] Writing Nginx HTTP config..."
sudo tee /etc/nginx/conf.d/greenspace.conf > /dev/null <<EOF
server {
    listen 80;
    server_name $APP_DOMAIN;
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
EOF
sudo nginx -t
sudo systemctl restart nginx

# Obtain SSL certificate using certbot standalone
echo "[user_data] Obtaining SSL certificate..."
if [ ! -f "/etc/letsencrypt/live/$APP_DOMAIN/fullchain.pem" ]; then
  sudo systemctl stop nginx
  sudo certbot certonly --standalone --non-interactive --agree-tos --email $LETSENCRYPT_EMAIL -d $APP_DOMAIN || {
    echo "[user_data] Certbot failed. Check logs for details.";
    sudo systemctl start nginx;
    exit 1;
  }
  sudo systemctl start nginx
  sudo nginx -t && sudo systemctl reload nginx
fi

# Write HTTPS config
echo "[user_data] Writing Nginx HTTPS config..."
sudo tee /etc/nginx/conf.d/greenspace-ssl.conf > /dev/null <<EOF
server {
    listen 443 ssl;
    server_name $APP_DOMAIN;
    ssl_certificate /etc/letsencrypt/live/$APP_DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$APP_DOMAIN/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name $APP_DOMAIN;
    return 301 https://\$server_name\$request_uri;
}
EOF
sudo nginx -t
sudo systemctl reload nginx

# Set up auto-renewal
echo "[user_data] Setting up certbot auto-renewal..."
if ! sudo crontab -l | grep -q 'certbot renew'; then
  echo "0 3 * * * certbot renew --quiet --post-hook 'nginx -t && systemctl reload nginx'" | sudo crontab -
fi

# Create systemd service for greenspace app
echo "[user_data] Creating systemd service for greenspace app..."
sudo tee /etc/systemd/system/greenspace.service > /dev/null <<EOF
[Unit]
Description=Greenspace FastAPI Application
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/greenspace-detection-platform/greenspace-app
Environment=PATH=/home/ec2-user/greenspace-detection-platform/greenspace-app/node_modules/.bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable greenspace
sudo systemctl start greenspace

echo "[user_data] Greenspace app setup complete at $(date)"
echo "[user_data] App should be available at https://$APP_DOMAIN"
