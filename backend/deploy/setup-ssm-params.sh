#!/bin/bash

# Setup AWS Systems Manager Parameters for UniversalAGI
# This script creates secure parameters in AWS SSM Parameter Store

set -e

ENVIRONMENT=${1:-production}
REGION=${2:-us-east-1}

echo "🔐 Setting up AWS SSM Parameters for environment: $ENVIRONMENT"

# Function to create secure parameter
create_secure_param() {
    local name=$1
    local value=$2
    local description=$3
    local param_name="/universalagi/$ENVIRONMENT/$name"
    
    # Check if parameter exists
    if aws ssm get-parameter --region $REGION --name "$param_name" >/dev/null 2>&1; then
        echo "📝 Parameter exists, updating: $param_name"
        # Update existing parameter
        aws ssm put-parameter \
            --region $REGION \
            --name "$param_name" \
            --value "$value" \
            --type "SecureString" \
            --description "$description" \
            --overwrite
        
        # Update tags separately
        aws ssm add-tags-to-resource \
            --region $REGION \
            --resource-type "Parameter" \
            --resource-id "$param_name" \
            --tags "Key=Environment,Value=$ENVIRONMENT" "Key=Application,Value=UniversalAGI" \
            >/dev/null 2>&1 || true
    else
        echo "🆕 Creating new parameter: $param_name"
        # Create new parameter with tags
        aws ssm put-parameter \
            --region $REGION \
            --name "$param_name" \
            --value "$value" \
            --type "SecureString" \
            --description "$description" \
            --tags "Key=Environment,Value=$ENVIRONMENT" "Key=Application,Value=UniversalAGI"
    fi
    
    echo "✅ Parameter ready: $param_name"
}

# Create parameters (you'll be prompted for each value)
echo "📝 Enter your configuration values:"

read -p "OpenAI API Key: " -s OPENAI_API_KEY
echo
create_secure_param "openai-api-key" "$OPENAI_API_KEY" "OpenAI API Key for UniversalAGI"

read -p "RDS Cluster ARN: " RDS_CLUSTER_ARN
create_secure_param "rds-cluster-arn" "$RDS_CLUSTER_ARN" "RDS Cluster ARN for database"

read -p "RDS Secret ARN: " RDS_SECRET_ARN
create_secure_param "rds-secret-arn" "$RDS_SECRET_ARN" "RDS Secret ARN for database credentials"

read -p "S3 Bucket Name: " S3_BUCKET_NAME
create_secure_param "s3-bucket-name" "$S3_BUCKET_NAME" "S3 bucket for file storage"

read -p "Allowed Origins (comma-separated): " ALLOWED_ORIGINS
create_secure_param "allowed-origins" "$ALLOWED_ORIGINS" "CORS allowed origins"

echo ""
echo "✅ All parameters created successfully!"
echo ""
echo "📋 To retrieve a parameter:"
echo "aws ssm get-parameter --region $REGION --name '/universalagi/$ENVIRONMENT/openai-api-key' --with-decryption"
echo ""
echo "🚀 Your EC2 instances can now fetch these securely using IAM roles!"
