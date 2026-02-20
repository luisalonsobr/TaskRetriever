#!/bin/bash
# Start WhatsApp Task Manager in background daemon mode

cd /Users/hardlou/dev/task-manager
python main.py watch > /tmp/whatsapp-tasks.log 2>&1 &
PID=$!
echo "WhatsApp Task Manager started with PID: $PID"
echo "Log: tail -f /tmp/whatsapp-tasks.log"
echo "Stop: kill $PID"
echo $PID > /tmp/whatsapp-tasks.pid