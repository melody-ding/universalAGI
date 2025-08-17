#!/bin/bash

# EC2 User Data Script for UniversalAGI Backend Deployment
# This script sets up the backend service on an Amazon Linux 2 EC2 instance

set -e

# Update system
yum update -y

# Install required packages
yum install -y \
    python3 \
    python3-pip \
    git \
    nginx \
    docker \
    awscli

# Start and enable services
systemctl start docker
systemctl enable docker
systemctl start nginx
systemctl enable nginx

# Add ec2-user to docker group
usermod -a -G docker ec2-user

# Create application directory
mkdir -p /opt/universalagi
chown ec2-user:ec2-user /opt/universalagi

# Create log directory
mkdir -p /var/log/universalagi
chown ec2-user:ec2-user /var/log/universalagi

# Create systemd service file
cat > /etc/systemd/system/universalagi-backend.service << EOF
[Unit]
Description=UniversalAGI Backend Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=ec2-user
Group=ec2-user
WorkingDirectory=/opt/universalagi/backend
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PYTHONPATH=/opt/universalagi/backend
EnvironmentFile=/opt/universalagi/.env

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/universalagi /var/log/universalagi /tmp

# Resource limits
LimitNOFILE=65536
MemoryMax=2G

[Install]
WantedBy=multi-user.target
EOF

# Create nginx configuration
cat > /etc/nginx/conf.d/universalagi.conf << EOF
server {
    listen 80;
    server_name _;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Rate limiting
    limit_req_zone \$binary_remote_addr zone=api:10m rate=10r/s;
    
    location / {
        limit_req zone=api burst=20 nodelay;
        
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 8k;
        proxy_buffers 8 8k;
        proxy_busy_buffers_size 16k;
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host \$host;
    }
    
    # Static files (if any)
    location /static/ {
        alias /opt/universalagi/backend/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# Test nginx configuration
nginx -t

# Reload nginx
systemctl reload nginx

# Create SSM environment fetcher script
cat > /opt/universalagi/fetch-env.sh << 'EOF'
#!/bin/bash
# Fetch environment variables from AWS SSM Parameter Store
ENVIRONMENT=${1:-production}
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
/opt/universalagi/backend/deploy/fetch-ssm-env.sh $ENVIRONMENT $REGION /opt/universalagi/.env
EOF

chmod +x /opt/universalagi/fetch-env.sh
chown ec2-user:ec2-user /opt/universalagi/fetch-env.sh

# Create environment file template (will be populated by deployment script)
cat > /opt/universalagi/.env.template << EOF
# This file will be populated during deployment
# See env.example for all available configuration options
ENVIRONMENT=production
DEBUG=false
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
EOF

chown ec2-user:ec2-user /opt/universalagi/.env.template

# Create deployment script
cat > /opt/universalagi/deploy.sh << 'EOF'
#!/bin/bash

# Deployment script for UniversalAGI Backend
set -e

REPO_URL=${REPO_URL:-"https://github.com/your-username/universalAGI.git"}
BRANCH=${BRANCH:-"main"}
DEPLOY_DIR="/opt/universalagi"

echo "Starting deployment..."

# Change to deployment directory
cd $DEPLOY_DIR

# Clone or update repository
if [ -d ".git" ]; then
    echo "Updating existing repository..."
    git fetch origin
    git reset --hard origin/$BRANCH
    git clean -fd
else
    echo "Cloning repository..."
    git clone -b $BRANCH $REPO_URL .
fi

# Install Python dependencies
echo "Installing Python dependencies..."
cd backend
pip3 install --user -r requirements.txt

# Fetch environment variables from SSM Parameter Store
echo "Fetching environment variables from AWS SSM Parameter Store..."
if /opt/universalagi/fetch-env.sh production; then
    echo "✅ Environment variables fetched successfully from SSM"
else
    echo "⚠️  Failed to fetch from SSM, using template..."
    if [ ! -f "/opt/universalagi/.env" ]; then
        cp /opt/universalagi/.env.template /opt/universalagi/.env
        echo "Please edit /opt/universalagi/.env with your configuration"
    fi
fi

# Restart the service
echo "Restarting application service..."
sudo systemctl daemon-reload
sudo systemctl restart universalagi-backend
sudo systemctl enable universalagi-backend

# Check service status
sleep 5
if systemctl is-active --quiet universalagi-backend; then
    echo "Deployment successful! Service is running."
else
    echo "Deployment failed! Service is not running."
    sudo systemctl status universalagi-backend
    exit 1
fi

echo "Deployment completed successfully!"
EOF

chmod +x /opt/universalagi/deploy.sh
chown ec2-user:ec2-user /opt/universalagi/deploy.sh

# Create a simple health check script
cat > /opt/universalagi/health-check.sh << 'EOF'
#!/bin/bash

# Health check script
HEALTH_URL="http://localhost/health"
MAX_RETRIES=3
RETRY_DELAY=5

for i in $(seq 1 $MAX_RETRIES); do
    if curl -f -s $HEALTH_URL > /dev/null; then
        echo "Health check passed"
        exit 0
    else
        echo "Health check failed (attempt $i/$MAX_RETRIES)"
        if [ $i -lt $MAX_RETRIES ]; then
            sleep $RETRY_DELAY
        fi
    fi
done

echo "Health check failed after $MAX_RETRIES attempts"
exit 1
EOF

chmod +x /opt/universalagi/health-check.sh
chown ec2-user:ec2-user /opt/universalagi/health-check.sh

# Create log rotation configuration
cat > /etc/logrotate.d/universalagi << EOF
/var/log/universalagi/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 ec2-user ec2-user
    postrotate
        systemctl reload universalagi-backend
    endscript
}
EOF

# Set up CloudWatch agent (optional)
if command -v amazon-cloudwatch-agent-ctl &> /dev/null; then
    cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << EOF
{
    "logs": {
        "logs_collected": {
            "files": {
                "collect_list": [
                    {
                        "file_path": "/var/log/universalagi/app.log",
                        "log_group_name": "/aws/ec2/universalagi/backend",
                        "log_stream_name": "{instance_id}",
                        "timestamp_format": "%Y-%m-%d %H:%M:%S"
                    }
                ]
            }
        }
    },
    "metrics": {
        "namespace": "UniversalAGI/Backend",
        "metrics_collected": {
            "cpu": {
                "measurement": ["cpu_usage_idle", "cpu_usage_iowait", "cpu_usage_user", "cpu_usage_system"],
                "metrics_collection_interval": 60
            },
            "disk": {
                "measurement": ["used_percent"],
                "metrics_collection_interval": 60,
                "resources": ["*"]
            },
            "mem": {
                "measurement": ["mem_used_percent"],
                "metrics_collection_interval": 60
            }
        }
    }
}
EOF

    # Start CloudWatch agent
    /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
        -a fetch-config \
        -m ec2 \
        -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json \
        -s
fi

echo "EC2 instance setup completed!"
echo "Next steps:"
echo "1. Edit /opt/universalagi/.env with your configuration"
echo "2. Run: sudo -u ec2-user /opt/universalagi/deploy.sh"
echo "3. Check service status: systemctl status universalagi-backend"
