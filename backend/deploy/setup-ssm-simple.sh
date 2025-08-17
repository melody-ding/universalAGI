#!/bin/bash

# Simple SSM Parameter Setup (no tags to avoid conflicts)
# This script creates secure parameters in AWS SSM Parameter Store

set -e

ENVIRONMENT=${1:-production}
REGION=${2:-us-east-1}

echo "🔐 Setting up AWS SSM Parameters (simple version)"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"

# Function to create/update parameter without tags
create_param() {
    local name=$1
    local value=$2
    local description=$3
    local param_name="/universalagi/$ENVIRONMENT/$name"
    
    echo "📝 Setting parameter: $param_name"
    
    aws ssm put-parameter \
        --region $REGION \
        --name "$param_name" \
        --value "$value" \
        --type "SecureString" \
        --description "$description" \
        --overwrite \
        --tier "Standard"
    
    echo "✅ Parameter set: $param_name"
}

# Get values from user or environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    read -p "OpenAI API Key: " -s OPENAI_API_KEY
    echo
fi

if [ -z "$RDS_CLUSTER_ARN" ]; then
    read -p "RDS Cluster ARN: " RDS_CLUSTER_ARN
fi

if [ -z "$RDS_SECRET_ARN" ]; then
    read -p "RDS Secret ARN: " RDS_SECRET_ARN
fi

if [ -z "$S3_BUCKET_NAME" ]; then
    read -p "S3 Bucket Name: " S3_BUCKET_NAME
fi

if [ -z "$ALLOWED_ORIGINS" ]; then
    read -p "Allowed Origins (comma-separated): " ALLOWED_ORIGINS
fi

# Create parameters
echo ""
echo "🚀 Creating/updating parameters..."

create_param "openai-api-key" "$OPENAI_API_KEY" "OpenAI API Key for UniversalAGI"
create_param "rds-cluster-arn" "$RDS_CLUSTER_ARN" "RDS Cluster ARN for database"
create_param "rds-secret-arn" "$RDS_SECRET_ARN" "RDS Secret ARN for database credentials"
create_param "s3-bucket-name" "$S3_BUCKET_NAME" "S3 bucket for file storage"
create_param "allowed-origins" "$ALLOWED_ORIGINS" "CORS allowed origins"

echo ""
echo "✅ All parameters created/updated successfully!"
echo ""
echo "📋 Parameters created:"
aws ssm describe-parameters \
    --region $REGION \
    --parameter-filters "Key=Name,Option=BeginsWith,Values=/universalagi/$ENVIRONMENT/" \
    --query 'Parameters[].Name' \
    --output table

echo ""
echo "🔍 To view a parameter value:"
echo "aws ssm get-parameter --region $REGION --name '/universalagi/$ENVIRONMENT/openai-api-key' --with-decryption --query 'Parameter.Value' --output text"
echo ""
echo "🗑️  To delete all parameters:"
echo "./backend/deploy/cleanup-ssm-params.sh $ENVIRONMENT $REGION"
