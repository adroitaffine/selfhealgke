#!/bin/bash

# GKE Auto-Heal Agent Dashboard Startup Script

set -e

echo "Starting GKE Auto-Heal Agent Dashboard..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

# Check if we're in the correct directory
if [ ! -f "server.py" ]; then
    echo "Error: server.py not found. Please run this script from the web-dashboard directory."
    exit 1
fi

# Install dependencies if requirements.txt exists and virtual environment is not active
if [ -f "requirements.txt" ] && [ -z "$VIRTUAL_ENV" ]; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
fi

# Set default environment variables
export DASHBOARD_HOST=${DASHBOARD_HOST:-"localhost"}
export DASHBOARD_PORT=${DASHBOARD_PORT:-"8080"}

echo "Dashboard will be available at: http://${DASHBOARD_HOST}:${DASHBOARD_PORT}"
echo "Demo credentials: admin/admin"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
python3 server.py