#!/usr/bin/env bash
# Greenspace Standalone App Launcher
# Double-click this file to run the Greenspace app

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    echo "Please install Python 3 and try again."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [[ ! -d "local_venv" ]]; then
    echo "Setting up Greenspace for first run..."
    python3 -m venv local_venv
    source local_venv/bin/activate
    pip install --upgrade pip
    pip install -r local_app/requirements.txt
    echo "Setup complete!"
else
    source local_venv/bin/activate
fi

# Start the server
echo "Starting Greenspace app..."
python local_app/main.py &
SERVER_PID=$!

# Wait a moment for server to start
sleep 2

# Open in default browser
if command -v open &> /dev/null; then
    open http://127.0.0.1:8000
elif command -v xdg-open &> /dev/null; then
    xdg-open http://127.0.0.1:8000
else
    echo "Greenspace is running at: http://127.0.0.1:8000"
    echo "Open this URL in your web browser."
fi

echo "Greenspace is running! Press Ctrl+C to stop."
wait $SERVER_PID