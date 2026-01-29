#!/bin/bash

# AWS SSO Configuration Script
# This script checks for existing AWS SSO configuration and helps set it up if needed

echo "Checking AWS SSO configuration..."

# Check if config file exists
if [ ! -f ~/.aws/config ]; then
    echo "No AWS config file found. Creating one..."
    mkdir -p ~/.aws
    touch ~/.aws/config
fi

# Check for existing SSO profiles
if grep -q "sso_start_url\|sso_session" ~/.aws/config; then
    echo "✅ AWS SSO is already configured!"
    echo ""
    echo "Found the following SSO profiles:"
    
    # Extract and display profile names
    profiles=$(grep -E "^\[profile " ~/.aws/config | sed 's/\[profile \(.*\)\]/\1/' | tr '\n' ' ')
    if [ -n "$profiles" ]; then
        echo "  Profiles: $profiles"
    fi
    
    # Extract and display SSO session names
    sessions=$(grep -E "^\[sso-session " ~/.aws/config | sed 's/\[sso-session \(.*\)\]/\1/' | tr '\n' ' ')
    if [ -n "$sessions" ]; then
        echo "  SSO Sessions: $sessions"
    fi
    
    echo ""
    echo "To use a specific profile, set the AWS_PROFILE environment variable:"
    echo "  export AWS_PROFILE=<profile-name>"
    echo ""
    echo "Then authenticate with:"
    echo "  aws sso login"
    echo "  (or: aws sso login --profile <profile-name> if using a specific profile)"
    echo ""
    exit 0
fi

# If no SSO config found, provide instructions
echo "No AWS SSO configuration found."
echo ""
echo "To configure AWS SSO, you can either:"
echo ""
echo "1. Run the interactive AWS CLI configuration:"
echo "   aws configure sso"
echo ""
echo "2. Or manually edit ~/.aws/config with your SSO settings"
echo ""
echo "You'll need:"
echo "  - SSO start URL"
echo "  - SSO region"
echo "  - SSO account ID"
echo "  - SSO role name"
echo ""
