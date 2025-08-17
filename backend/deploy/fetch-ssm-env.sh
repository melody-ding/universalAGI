#!/bin/bash

# Fetch environment variables from AWS SSM Parameter Store
# This script creates a .env file from SSM parameters

set -e

ENVIRONMENT=${1:-production}
REGION=${2:-us-east-1}
OUTPUT_FILE=${3:-/opt/universalagi/.env}

echo "🔐 Fetching environment variables from AWS SSM Parameter Store..."
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Output: $OUTPUT_FILE"

# Function to fetch and export parameter
fetch_param() {
    local param_name=$1
    local env_var_name=$2
    local default_value=$3
    
    local full_param_name="/universalagi/$ENVIRONMENT/$param_name"
    
    # Try to fetch the parameter
    local value=$(aws ssm get-parameter \
        --region $REGION \
        --name "$full_param_name" \
        --with-decryption \
        --query 'Parameter.Value' \
        --output text 2>/dev/null || echo "$default_value")
    
    if [ "$value" != "$default_value" ] && [ "$value" != "None" ]; then
        echo "$env_var_name=$value" >> $OUTPUT_FILE
        echo "✅ Fetched: $env_var_name"
    else
        echo "⚠️  Warning: Could not fetch $param_name, using default: $default_value"
        echo "$env_var_name=$default_value" >> $OUTPUT_FILE
    fi
}

# Create directory if it doesn't exist
mkdir -p $(dirname $OUTPUT_FILE)

# Create new .env file
cat > $OUTPUT_FILE << EOF
# Environment variables fetched from AWS SSM Parameter Store
# Generated on: $(date)
# Environment: $ENVIRONMENT

# Basic Configuration
ENVIRONMENT=$ENVIRONMENT
DEBUG=false
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
MAX_CONVERSATION_HISTORY=5
CORS_ALLOW_CREDENTIALS=true

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/var/log/universalagi/app.log
LOG_CONSOLE=true

# AWS Configuration (using IAM role, no explicit credentials needed)
AWS_REGION=$REGION

EOF

# Fetch secure parameters
fetch_param "openai-api-key" "OPENAI_API_KEY" "your_openai_api_key_here"
fetch_param "rds-cluster-arn" "RDS_CLUSTER_ARN" "your-rds-cluster-arn"
fetch_param "rds-secret-arn" "RDS_SECRET_ARN" "your-rds-secret-arn"
fetch_param "s3-bucket-name" "S3_BUCKET_NAME" "your-s3-bucket-name"
fetch_param "allowed-origins" "ALLOWED_ORIGINS" "https://yourdomain.com"

# Add static OpenAI configuration
cat >> $OUTPUT_FILE << EOF

# OpenAI Configuration
OPENAI_MODEL_NAME=gpt-4o
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_TOKENS=4000

# Database Configuration
RDS_DATABASE_NAME=postgres

# Agent Configuration (using defaults)
ROUTER_WEIGHT_AVG_VEC_SIM=0.9
ROUTER_WEIGHT_FTS_HIT_RATE=0.5
ROUTER_WEIGHT_TOP_DOC_SHARE=0.8
ROUTER_WEIGHT_UNIQUE_DOCS=-0.7
ROUTER_WEIGHT_QUOTES_IDS=-0.1
ROUTER_WEIGHT_TEMPORAL=-0.6
ROUTER_THRESHOLD=0.5

ESCALATION_MIN_STRONG_SEGMENTS=2
ESCALATION_MAX_DISTINCT_DOCS=4
ESCALATION_MIN_AVG_VEC_SIM=0.60
ESCALATION_MIN_FTS_HIT_RATE=0.10

AGENT_PROBE_DOC_LIMIT=10
AGENT_PROBE_CANDIDATES_PER_TYPE=3
AGENT_SHORT_TOP_DOCS=15
AGENT_SHORT_PER_DOC=3
AGENT_SHORT_VECTOR_LIMIT=20
AGENT_SHORT_TEXT_LIMIT=20
AGENT_SHORT_ALPHA=0.6
AGENT_LONG_MAX_SUBQUERIES=3
AGENT_LONG_MAX_STEPS=5
AGENT_LONG_BUDGET_TOKENS=8000
AGENT_LONG_BUDGET_TIME_SEC=30
AGENT_MAX_RESPONSE_TOKENS=4000
AGENT_MAX_CONTEXT_TOKENS=12000
AGENT_MAX_CONTEXT_CHARS=48000
EOF

# Set appropriate permissions
chmod 600 $OUTPUT_FILE
chown ec2-user:ec2-user $OUTPUT_FILE 2>/dev/null || true

echo ""
echo "✅ Environment file created successfully: $OUTPUT_FILE"
echo "🔒 File permissions set to 600 (owner read/write only)"
echo ""
echo "🚀 To use this configuration:"
echo "sudo systemctl restart universalagi-backend"
