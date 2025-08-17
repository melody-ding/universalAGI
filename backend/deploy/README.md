# UniversalAGI Backend Deployment Guide

This directory contains everything needed to deploy the UniversalAGI backend to AWS EC2.

## Quick Start

1. **Prerequisites**
   - AWS CLI configured with appropriate permissions
   - Terraform installed (if using Terraform deployment)
   - SSH key pair created in AWS

2. **Manual EC2 Deployment**
   ```bash
   # Launch an EC2 instance with userdata.sh as the user data script
   # Then SSH into the instance and run:
   sudo -u ec2-user /opt/universalagi/deploy.sh
   ```

3. **Terraform Deployment**
   ```bash
   cd terraform/
   terraform init
   terraform plan -var="key_name=your-key-name" -var="openai_api_key=sk-..."
   terraform apply
   ```

## Configuration Management

The backend now uses a consolidated configuration system with environment variables:

### Environment Variables

All configuration is managed through environment variables. See `env.example` for a complete list.

**Critical Variables:**
- `OPENAI_API_KEY` - Required for AI functionality
- `RDS_CLUSTER_ARN` - RDS Data API cluster ARN
- `RDS_SECRET_ARN` - RDS Data API secret ARN  
- `S3_BUCKET_NAME` - S3 bucket for file storage
- `ENVIRONMENT` - Set to "production" for production deployment

### Configuration Structure

The new config system (`backend/config.py`) provides:

- **Type-safe configuration** with dataclasses and enums
- **Environment-specific settings** (development, staging, production)
- **Validation** for critical configuration in non-development environments
- **Backward compatibility** with existing code
- **Centralized AWS, database, and OpenAI settings**

## Files Overview

### Core Deployment Files

- `userdata.sh` - EC2 user data script for automated setup
- `env.example` - Complete environment variable template
- `env.template` - Terraform template for environment variables

### Terraform Infrastructure

- `terraform/main.tf` - Complete AWS infrastructure as code
  - VPC with public subnets
  - Application Load Balancer
  - Auto Scaling Group
  - Security Groups
  - IAM roles and policies
  - Systems Manager parameters

### Scripts

- `deploy.sh` - Application deployment script (created by userdata.sh)
- `health-check.sh` - Health monitoring script (created by userdata.sh)

## Infrastructure Components

### EC2 Setup
- Amazon Linux 2 instances
- Nginx reverse proxy
- SystemD service management
- CloudWatch monitoring (optional)
- Log rotation

### Security
- Security groups with minimal required access
- IAM roles for AWS service access (no hardcoded credentials)
- SSL/TLS termination at load balancer
- Security headers and rate limiting

### Monitoring
- Health check endpoint at `/health`
- CloudWatch logs and metrics
- Log rotation for application logs
- Service monitoring via SystemD

## Deployment Process

### 1. Infrastructure Setup (Terraform)

```bash
cd terraform/

# Initialize Terraform
terraform init

# Plan deployment
terraform plan \
  -var="key_name=your-ec2-key" \
  -var="openai_api_key=sk-your-openai-key" \
  -var="rds_cluster_arn=arn:aws:rds:..." \
  -var="rds_secret_arn=arn:aws:secretsmanager:..." \
  -var="s3_bucket_name=your-bucket-name" \
  -var="domain_name=yourdomain.com"

# Apply infrastructure
terraform apply
```

### 2. Manual EC2 Setup

If not using Terraform, launch an EC2 instance with:
- Amazon Linux 2 AMI
- t3.medium or larger instance type
- User data script: `userdata.sh`
- Security group allowing HTTP(S) and SSH
- IAM role with RDS Data API, S3, and CloudWatch permissions

### 3. Application Deployment

SSH into the instance and run:

```bash
# Edit environment configuration
sudo vi /opt/universalagi/.env

# Deploy application
sudo -u ec2-user /opt/universalagi/deploy.sh

# Check service status
systemctl status universalagi-backend

# Check health
curl http://localhost/health
```

## Post-Deployment

### Service Management

```bash
# View logs
journalctl -u universalagi-backend -f

# Restart service
sudo systemctl restart universalagi-backend

# Check nginx status
sudo systemctl status nginx

# View application logs
tail -f /var/log/universalagi/app.log
```

### Health Monitoring

The application provides a health check endpoint:

```bash
curl http://your-domain/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": 1640995200.0,
  "version": "1.0.0", 
  "environment": "production"
}
```

### Scaling

The Terraform configuration includes an Auto Scaling Group that can:
- Scale from 1 to 3 instances based on demand
- Automatically replace unhealthy instances
- Distribute traffic via Application Load Balancer

## Troubleshooting

### Common Issues

1. **Service won't start**
   ```bash
   # Check service logs
   journalctl -u universalagi-backend -n 50
   
   # Check environment file
   cat /opt/universalagi/.env
   
   # Verify permissions
   ls -la /opt/universalagi/
   ```

2. **Database connection issues**
   ```bash
   # Verify RDS Data API permissions
   aws rds-data execute-statement --help
   
   # Check IAM role
   aws sts get-caller-identity
   ```

3. **Missing dependencies**
   ```bash
   # Reinstall Python packages
   cd /opt/universalagi/backend
   pip3 install --user -r requirements.txt
   ```

### Logs Location

- Application logs: `/var/log/universalagi/app.log`
- Service logs: `journalctl -u universalagi-backend`
- Nginx logs: `/var/log/nginx/`

## Security Best Practices

1. **Secrets Management**
   - Use AWS Systems Manager Parameter Store for sensitive values
   - Never commit secrets to version control
   - Rotate API keys regularly

2. **Network Security**
   - Use security groups to restrict access
   - Consider using private subnets for database
   - Enable VPC Flow Logs

3. **Instance Security**
   - Keep system packages updated
   - Use IAM roles instead of access keys
   - Enable CloudTrail for audit logging

## Updating Configuration

The consolidated config system makes updates easier:

1. **Environment Variables**: Update `/opt/universalagi/.env`
2. **Code Changes**: Re-run deployment script
3. **Infrastructure**: Use Terraform to apply changes

This replaces the previous scattered configuration across multiple files with a single, type-safe, validated configuration system.
