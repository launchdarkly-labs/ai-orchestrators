#!/bin/bash

# AWS SSO Login Helper
# Reads AWS_PROFILE from .env file and authenticates

# Get the project root directory (same directory as this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
ENV_FILE="$PROJECT_ROOT/.env"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ .env file not found at $ENV_FILE"
    echo "Please create it by copying .env.example:"
    echo "  cp .env.example .env"
    exit 1
fi

# Read AWS_PROFILE from .env
if [ -f "$ENV_FILE" ]; then
    # Extract AWS_PROFILE value, handling comments and whitespace
    PROFILE=$(grep -E "^AWS_PROFILE=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' ' | tr -d '"' | tr -d "'")
    
    if [ -z "$PROFILE" ]; then
        echo "❌ AWS_PROFILE not found in .env file"
        echo "Please add AWS_PROFILE=your-profile-name to $ENV_FILE"
        exit 1
    fi
    
    echo "Using AWS profile from .env: $PROFILE"
    echo "Authenticating with AWS SSO..."
    aws sso login --profile "$PROFILE"
else
    echo "❌ .env file not found"
    exit 1
fi
