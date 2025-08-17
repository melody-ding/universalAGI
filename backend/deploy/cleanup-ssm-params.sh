#!/bin/bash

# Cleanup SSM Parameters for UniversalAGI
# This script removes all parameters for a given environment

set -e

ENVIRONMENT=${1:-production}
REGION=${2:-us-east-1}

echo "🗑️  Cleaning up AWS SSM Parameters for environment: $ENVIRONMENT"
echo "Region: $REGION"

# Get all parameters for this environment
PARAMS=$(aws ssm describe-parameters \
    --region $REGION \
    --parameter-filters "Key=Name,Option=BeginsWith,Values=/universalagi/$ENVIRONMENT/" \
    --query 'Parameters[].Name' \
    --output text)

if [ -z "$PARAMS" ]; then
    echo "ℹ️  No parameters found for environment: $ENVIRONMENT"
    exit 0
fi

echo ""
echo "📋 Found parameters:"
echo "$PARAMS" | tr '\t' '\n'

echo ""
read -p "❓ Are you sure you want to delete these parameters? (y/N): " confirm

if [[ $confirm =~ ^[Yy]$ ]]; then
    echo ""
    echo "🗑️  Deleting parameters..."
    
    for param in $PARAMS; do
        echo "Deleting: $param"
        aws ssm delete-parameter \
            --region $REGION \
            --name "$param"
        echo "✅ Deleted: $param"
    done
    
    echo ""
    echo "✅ All parameters deleted successfully!"
else
    echo "❌ Operation cancelled"
fi
