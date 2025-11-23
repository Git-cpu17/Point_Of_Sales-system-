#!/bin/bash

# Azure deployment script for Node.js application
# This script is executed during Azure App Service deployment

# Exit on error
set -e

echo "Starting deployment..."

# 1. Install dependencies
echo "Installing npm dependencies..."
npm install --production

# 2. Verify server.js exists
if [ ! -f server.js ]; then
  echo "Error: server.js not found!"
  exit 1
fi

# 3. Verify db.js exists
if [ ! -f db.js ]; then
  echo "Error: db.js not found!"
  exit 1
fi

# 4. Check if views directory exists
if [ ! -d views ]; then
  echo "Error: views directory not found!"
  exit 1
fi

# 5. Check if static directory exists
if [ ! -d static ]; then
  echo "Error: static directory not found!"
  exit 1
fi

echo "Deployment completed successfully!"
