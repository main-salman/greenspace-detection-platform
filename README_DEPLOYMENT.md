# Greenspace App AWS Deployment

This directory contains Terraform configuration and scripts to deploy the Greenspace vegetation analysis application on AWS.

## 🚀 Quick Start

### Prerequisites

1. **AWS Account**: Ensure you have AWS credentials in the `.env` file:
   ```
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   ```

2. **Terraform**: Install Terraform from [terraform.io](https://www.terraform.io/downloads)

3. **Domain**: Ensure you have the `qolimpact.click` domain configured in Route53

4. **SSH Key**: Ensure you have the `salman-dev.pem` key pair in AWS and the private key file locally

### Deployment Steps

1. **Configure Variables**: Update `terraform.tfvars` with your Route53 zone ID:
   ```hcl
   route53_zone_id = "Z04728076IFR45VRDTS8"  # Your actual zone ID
   ```

2. **Deploy Infrastructure**:
   ```bash
   ./deploy.sh
   ```

3. **Wait for Setup**: The initial setup takes 5-10 minutes for:
   - EC2 instance initialization
   - SSL certificate generation
   - Application build and startup

4. **Access Your App**: Visit `https://greenspace.qolimpact.click`

## 📁 Files Overview

### Infrastructure
- `main.tf` - Terraform configuration for AWS resources
- `terraform.tfvars` - Configuration variables
- `user_data.sh` - EC2 initialization script

### Management Scripts
- `deploy.sh` - Complete deployment script
- `update_ec2.sh` - Update application code on existing instance
- `troubleshoot.sh` - Diagnostic and troubleshooting script

## 🏗️ Architecture

The deployment creates:

- **EC2 Instance**: t3.medium with 50GB storage running Amazon Linux 2
- **Security Group**: Allows HTTP (80), HTTPS (443), SSH (22), and app port (8000)
- **Route53 Record**: DNS A record pointing to the EC2 public IP
- **SSL Certificate**: Automatic Let's Encrypt certificate via Certbot
- **Nginx**: Reverse proxy with HTTPS redirect
- **Systemd Service**: Auto-starting Greenspace application service

## 🔧 Management Commands

### Update Application
```bash
./update_ec2.sh
```

### Troubleshoot Issues
```bash
./troubleshoot.sh
```

### SSH to Instance
```bash
ssh -i salman-dev.pem ec2-user@$(terraform output -raw ec2_public_ip)
```

### View Terraform Outputs
```bash
terraform output
```

## 🔍 Monitoring

### Application Logs
```bash
# On EC2 instance
sudo journalctl -u greenspace -f
tail -f /home/ec2-user/greenspace-mei/greenspace_app.log
```

### Nginx Logs
```bash
# On EC2 instance
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## 🛠️ Troubleshooting

### Common Issues

1. **App Not Loading**:
   - Check if service is running: `sudo systemctl status greenspace`
   - Check application logs: `tail -f /home/ec2-user/greenspace-mei/greenspace_app.log`
   - Restart service: `sudo systemctl restart greenspace`

2. **SSL Certificate Issues**:
   - Check certificate: `sudo certbot certificates`
   - Renew certificate: `sudo certbot renew`
   - Check nginx config: `sudo nginx -t`

3. **DNS Issues**:
   - Verify Route53 record points to correct IP
   - Check if domain propagation is complete: `nslookup greenspace.qolimpact.click`

### Manual Service Management

```bash
# Start/stop/restart the application
sudo systemctl start greenspace
sudo systemctl stop greenspace
sudo systemctl restart greenspace

# View service status
sudo systemctl status greenspace

# Enable/disable auto-start
sudo systemctl enable greenspace
sudo systemctl disable greenspace
```

## 🔐 Security

- SSH access is configured for the `salman-dev` key pair
- Security group allows necessary ports only
- SSL/TLS encryption via Let's Encrypt
- Application runs as non-root user (`ec2-user`)

## 💰 Cost Estimation

- **EC2 t3.medium**: ~$30/month
- **EBS 50GB**: ~$5/month
- **Data Transfer**: Variable based on usage
- **Route53**: ~$0.50/month per hosted zone

**Total**: ~$35-40/month

## 🗑️ Cleanup

To destroy all resources:
```bash
terraform destroy
```

**Warning**: This will permanently delete the EC2 instance and all data.

## 📞 Support

For issues or questions:
1. Run `./troubleshoot.sh` for diagnostic information
2. Check application and system logs
3. Verify AWS resource status in the console
