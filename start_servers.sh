#!/bin/bash
# Script to start both the Next.js app and the Alignment Testing API

echo "🚀 Starting Greenspace Analysis Platform"
echo "========================================"

# Function to handle cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    kill $ALIGNMENT_PID 2>/dev/null
    kill $NEXTJS_PID 2>/dev/null
    exit 0
}

# Set trap for cleanup on script exit
trap cleanup SIGINT SIGTERM

# Start the Alignment Testing API in background
echo "📡 Starting Alignment Testing API on port 5001..."
source alignment_venv/bin/activate
python web_alignment_tester.py &
ALIGNMENT_PID=$!

# Wait a moment for API to start
sleep 3

# Check if API started successfully
if curl -s http://localhost:5001/health > /dev/null; then
    echo "✅ Alignment Testing API started successfully"
else
    echo "❌ Failed to start Alignment Testing API"
    exit 1
fi

# Start Next.js development server
echo "🌐 Starting Next.js app on port 3000..."
cd greenspace-app
npm run dev &
NEXTJS_PID=$!

echo ""
echo "🎉 Both servers are running!"
echo "📱 Next.js App: http://localhost:3000"
echo "🔧 Alignment API: http://localhost:5001"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for background processes
wait