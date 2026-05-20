#!/bin/bash
# Restart the ThinAI backend server

# Kill any existing server
lsof -ti:8000 | xargs kill -9 2>/dev/null
sleep 1

# Start from project root using module syntax
cd "$(dirname "$0")"
python3 -m engine.api &

echo "Server starting on http://localhost:8000"
