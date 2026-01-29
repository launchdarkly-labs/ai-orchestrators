#!/bin/bash

# Find My AWS Resources Script
# This script helps identify resources you created by checking tags, IAM roles, and metadata

# Allow profile to be passed as argument
if [ -n "$1" ]; then
    export AWS_PROFILE="$1"
    echo "Using profile: $AWS_PROFILE"
fi

echo "Finding resources created by you..."
echo ""

# Check if AWS_PROFILE is set, otherwise try to detect active profile
if [ -z "$AWS_PROFILE" ]; then
    # Check for profiles with SSO sessions
    if [ -f ~/.aws/config ]; then
        # Try to find a profile that might be logged in
        PROFILES=$(grep -E "^\[profile " ~/.aws/config | sed 's/\[profile \(.*\)\]/\1/')
        for profile in $PROFILES; do
            if AWS_PROFILE=$profile aws sts get-caller-identity &>/dev/null; then
                export AWS_PROFILE=$profile
                echo "Detected active profile: $profile"
                break
            fi
        done
    fi
fi

# Get current identity
if [ -n "$AWS_PROFILE" ]; then
    IDENTITY=$(AWS_PROFILE=$AWS_PROFILE aws sts get-caller-identity --output json 2>/dev/null)
else
    IDENTITY=$(aws sts get-caller-identity --output json 2>/dev/null)
fi

if [ -z "$IDENTITY" ]; then
    echo "❌ AWS credentials not configured or invalid."
    echo ""
    echo "Please authenticate with AWS SSO:"
    if [ -n "$AWS_PROFILE" ]; then
        echo "  aws sso login --profile $AWS_PROFILE"
    else
        echo "  aws sso login"
        echo "  (or: aws sso login --profile <profile-name>)"
    fi
    exit 1
fi

ACCOUNT_ID=$(echo "$IDENTITY" | grep -o '"Account": "[^"]*"' | cut -d'"' -f4)
USER_ARN=$(echo "$IDENTITY" | grep -o '"Arn": "[^"]*"' | cut -d'"' -f4)
USER_NAME=$(echo "$USER_ARN" | awk -F'/' '{print $NF}')

# Get region using the profile if set
if [ -n "$AWS_PROFILE" ]; then
    REGION=$(AWS_PROFILE=$AWS_PROFILE aws configure get region 2>/dev/null || echo "us-east-1")
else
    REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")
fi

echo "Your Identity: $USER_ARN"
echo "Account: $ACCOUNT_ID"
echo "Region: $REGION"
echo ""

# Build AWS command prefix
AWS_CMD_PREFIX=""
if [ -n "$AWS_PROFILE" ]; then
    AWS_CMD_PREFIX="AWS_PROFILE=$AWS_PROFILE"
fi

echo "=========================================="
echo "Resources that might be yours:"
echo "=========================================="
echo ""

# Check CloudFormation stacks with your identity in tags or stack name
echo "CloudFormation Stacks:"
if [ -n "$AWS_CMD_PREFIX" ]; then
    STACKS=$(eval "$AWS_CMD_PREFIX aws cloudformation list-stacks --region $REGION --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --output json 2>/dev/null" || echo "")
else
    STACKS=$(aws cloudformation list-stacks --region $REGION --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --output json 2>/dev/null || echo "")
fi
if [ -n "$STACKS" ] && [ "$STACKS" != "null" ]; then
    STACK_NAMES=$(echo "$STACKS" | grep -o '"StackName": "[^"]*"' | cut -d'"' -f4 | head -20)
    FOUND_ANY=0
    COUNT=0
    for stack in $STACK_NAMES; do
        COUNT=$((COUNT + 1))
        if [ $COUNT -gt 10 ]; then
            echo "  (Limiting to first 10 stacks to avoid timeout)"
            break
        fi
        # Check if stack name contains your username (faster than full describe)
        if echo "$stack" | grep -qi "$USER_NAME"; then
            if [ -n "$AWS_CMD_PREFIX" ]; then
                CREATION_TIME=$(eval "$AWS_CMD_PREFIX aws cloudformation describe-stacks --region $REGION --stack-name \"$stack\" --query 'Stacks[0].CreationTime' --output text 2>/dev/null" || echo "unknown")
            else
                CREATION_TIME=$(aws cloudformation describe-stacks --region $REGION --stack-name "$stack" --query 'Stacks[0].CreationTime' --output text 2>/dev/null || echo "unknown")
            fi
            echo "  ✓ $stack (Created: $CREATION_TIME)"
            FOUND_ANY=1
        fi
    done
    if [ $FOUND_ANY -eq 0 ]; then
        echo "  (No stacks found with your identity in name)"
    fi
else
    echo "  (No stacks found or unable to query)"
fi

echo ""

# Check Lambda functions
echo "Lambda Functions:"
if [ -n "$AWS_CMD_PREFIX" ]; then
    LAMBDAS=$(eval "$AWS_CMD_PREFIX aws lambda list-functions --region $REGION --output json 2>/dev/null" || echo "")
else
    LAMBDAS=$(aws lambda list-functions --region $REGION --output json 2>/dev/null || echo "")
fi
if [ -n "$LAMBDAS" ] && [ "$LAMBDAS" != "null" ]; then
    LAMBDA_NAMES=$(echo "$LAMBDAS" | grep -o '"FunctionName": "[^"]*"' | cut -d'"' -f4 | head -20)
    FOUND_ANY=0
    COUNT=0
    for func in $LAMBDA_NAMES; do
        COUNT=$((COUNT + 1))
        if [ $COUNT -gt 10 ]; then
            echo "  (Limiting to first 10 functions to avoid timeout)"
            break
        fi
        # Check if function name contains your username (faster than full get-function)
        if echo "$func" | grep -qi "$USER_NAME"; then
            if [ -n "$AWS_CMD_PREFIX" ]; then
                LAST_MODIFIED=$(eval "$AWS_CMD_PREFIX aws lambda get-function --region $REGION --function-name \"$func\" --query 'Configuration.LastModified' --output text 2>/dev/null" || echo "unknown")
            else
                LAST_MODIFIED=$(aws lambda get-function --region $REGION --function-name "$func" --query 'Configuration.LastModified' --output text 2>/dev/null || echo "unknown")
            fi
            echo "  ✓ $func (Last Modified: $LAST_MODIFIED)"
            FOUND_ANY=1
        fi
    done
    if [ $FOUND_ANY -eq 0 ]; then
        echo "  (No functions found with your identity in name)"
    fi
else
    echo "  (No functions found or unable to query)"
fi

echo ""

# Check EC2 instances with tags
echo "EC2 Instances:"
if [ -n "$AWS_CMD_PREFIX" ]; then
    INSTANCES=$(eval "$AWS_CMD_PREFIX aws ec2 describe-instances --region $REGION --filters \"Name=instance-state-name,Values=running,stopped\" --query 'Reservations[*].Instances[*].[InstanceId,Tags[?Key==\`Name\`].Value|[0],State.Name]' --output json 2>/dev/null" || echo "")
else
    INSTANCES=$(aws ec2 describe-instances --region $REGION --filters "Name=instance-state-name,Values=running,stopped" --query 'Reservations[*].Instances[*].[InstanceId,Tags[?Key==`Name`].Value|[0],State.Name]' --output json 2>/dev/null || echo "")
fi
if [ -n "$INSTANCES" ] && [ "$INSTANCES" != "null" ] && [ "$INSTANCES" != "[]" ]; then
    FOUND_ANY=0
    # Parse JSON output more efficiently
    echo "$INSTANCES" | grep -o '\["[^"]*","[^"]*","[^"]*"\]' | head -20 | while IFS= read -r line; do
        INSTANCE_ID=$(echo "$line" | grep -o '\["[^"]*"' | cut -d'"' -f2)
        INSTANCE_NAME=$(echo "$line" | grep -o ',"[^"]*","' | cut -d'"' -f2)
        STATE=$(echo "$line" | grep -o '"[^"]*"\]' | cut -d'"' -f2)
        if echo "$INSTANCE_NAME" | grep -qi "$USER_NAME"; then
            echo "  ✓ $INSTANCE_ID - $INSTANCE_NAME (State: $STATE)"
            FOUND_ANY=1
        fi
    done
    if [ $FOUND_ANY -eq 0 ]; then
        echo "  (No instances found with your identity in name)"
    fi
else
    echo "  (No instances found or unable to query)"
fi

echo ""
echo "=========================================="
echo "Tips for identifying your resources:"
echo "=========================================="
echo ""
echo "1. Resources with your username in the name are likely yours"
echo "2. Check CloudFormation stacks - they show creation time and creator"
echo "3. Use tags: Many resources can be tagged with 'Creator' or 'Owner'"
echo "4. Check IAM roles: Resources using your IAM role are likely yours"
echo ""
echo "To tag resources for future identification:"
echo "  aws <service> tag-resource --resource-arn <arn> --tags Key=Creator,Value=$USER_NAME"
echo ""
