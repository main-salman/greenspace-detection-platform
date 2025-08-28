# main.tf
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "notification_email" {
  description = "Email for notifications"
  type        = string
  default     = "salman.naqvi@gmail.com"
}

variable "app_domain" {
  description = "Domain name for the Greenspace app (used for HTTPS cert)"
  type        = string
  default     = "greenspace.qolimpact.click"
}

variable "letsencrypt_email" {
  description = "Email for Let's Encrypt certificate registration"
  type        = string
  default     = "salman.naqvi@gmail.com"
}

variable "route53_zone_id" {
  description = "Route53 Hosted Zone ID for the domain (e.g., Z123456ABCDEFG)"
  type        = string
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# VPC and networking (using default VPC for simplicity)
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Security Group for EC2 instances
resource "aws_security_group" "greenspace_workers" {
  name_prefix = "greenspace-workers-"
  vpc_id      = data.aws_vpc.default.id

  # Allow HTTP access
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow HTTPS access
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow FastAPI app port 8000
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow SSH access
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "greenspace-workers"
  }
}

# IAM role for EC2 instances (minimal permissions for greenspace app)
resource "aws_iam_role" "ec2_greenspace_role" {
  name = "EC2GreenspaceWorkerRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

# Basic policy for EC2 instance (no S3 or other services needed)
resource "aws_iam_role_policy" "ec2_greenspace_policy" {
  name = "EC2GreenspaceWorkerPolicy"
  role = aws_iam_role.ec2_greenspace_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_greenspace_profile" {
  name = "EC2GreenspaceWorkerProfile"
  role = aws_iam_role.ec2_greenspace_role.name
}

# EC2 Instance for Greenspace App
resource "aws_instance" "greenspace_manager" {
  ami                    = "ami-0e95a5e2743ec9ec9" # Latest Amazon Linux 2 AMI for us-east-1
  instance_type          = "t3.medium"

  root_block_device {
    volume_size = 50
    volume_type = "gp3"
  }

  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.greenspace_workers.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_greenspace_profile.name
  user_data              = base64encode(templatefile("${path.module}/user_data.sh", {
    AWS_REGION = var.aws_region,
    APP_DOMAIN = var.app_domain,
    LETSENCRYPT_EMAIL = var.letsencrypt_email
  }))
  key_name               = "salman-dev" # Use the salman-dev key pair for SSH access
  
  tags = {
    Name = "greenspace-manager"
  }
}

# Route53 DNS record
resource "aws_route53_record" "app" {
  zone_id = var.route53_zone_id
  name    = var.app_domain
  type    = "A"
  ttl     = 300
  records = [aws_instance.greenspace_manager.public_ip]
}

# --- Outputs for EC2 Instance ---
output "ec2_instance_id" {
  description = "EC2 Instance ID"
  value       = aws_instance.greenspace_manager.id
}

output "ec2_public_ip" {
  description = "EC2 Public IP"
  value       = aws_instance.greenspace_manager.public_ip
}

output "ec2_private_ip" {
  description = "EC2 Private IP"
  value       = aws_instance.greenspace_manager.private_ip
}

output "app_url" {
  description = "HTTPS URL for the Greenspace app"
  value       = "https://${var.app_domain}"
}

output "app_dns_record" {
  description = "Route53 record for the app domain"
  value       = aws_route53_record.app.fqdn
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i salman-dev.pem ec2-user@${aws_instance.greenspace_manager.public_ip}"
}
