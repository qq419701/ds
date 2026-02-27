#!/bin/bash
pkill -f "gunicorn.*run:app"
echo "✅ 应用已停止"
