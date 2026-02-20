#!/bin/bash
# Stop WhatsApp Task Manager daemon

if [ -f /tmp/whatsapp-tasks.pid ]; then
    PID=$(cat /tmp/whatsapp-tasks.pid)
    if ps -p $PID > /dev/null; then
        kill $PID
        echo "WhatsApp Task Manager stopped (PID: $PID)"
        rm /tmp/whatsapp-tasks.pid
    else
        echo "Process not running"
        rm /tmp/whatsapp-tasks.pid
    fi
else
    echo "PID file not found"
fi