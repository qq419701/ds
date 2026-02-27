#!/bin/bash
pkill -f "gunicorn.*run:app"
echo "服务已停止"
