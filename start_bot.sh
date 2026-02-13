#!/bin/bash
# Market Lens Bot - Restart Script

echo "🛑 Stopping old instances..."
pkill -f "marketlens-bot" || true
pkill -f "python3 bot/main.py" || true
pkill -f "python.*bot/main.py" || true

echo "⏳ Waiting for cleanup..."
sleep 2

echo "🚀 Starting Market Lens Bot (v3.7)..."
export PYTHONPATH=$PYTHONPATH:.

# Run in background and log to file
nohup python3 bot/main.py > bot.log 2>&1 &
PID=$!

echo "✅ Bot started with PID $PID"
echo "📜 Tailing logs (5 seconds)..."
sleep 5

if ps -p $PID > /dev/null; then
    echo "🟢 STATUS: RUNNING"
    echo "--- LOG START ---"
    tail -n 10 bot.log
    echo "--- LOG END ---"
else
    echo "🔴 STATUS: FAILED"
    echo "--- LOG ERROR ---"
    cat bot.log
    echo "--- LOG END ---"
fi
