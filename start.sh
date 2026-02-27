#!/bin/bash
cd /www/wwwroot/ds
source venv/bin/activate
mkdir -p logs
gunicorn -c gunicorn_conf.py run:app --daemon
echo "服务已启动"
