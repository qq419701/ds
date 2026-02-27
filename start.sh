#!/bin/bash
cd /www/wwwroot/ds
source venv/bin/activate
export PYTHONPATH=/www/wwwroot/ds:$PYTHONPATH
/www/wwwroot/ds/venv/bin/gunicorn -c gunicorn_conf.py run:app -D
echo "✅ 应用已启动"
