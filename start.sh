#!/bin/bash
cd /www/wwwroot/dianshang
source venv/bin/activate
export PYTHONPATH=/www/wwwroot/dianshang:$PYTHONPATH
export DATABASE_URL='mysql+pymysql://dianshang:HkW6F2PTKaKaCMnm@localhost:3306/dianshang?charset=utf8mb4'
export SECRET_KEY='a8f5f167f44f4964e6c998dee827110c3eb2c6b4f8a6d8e2c3d9f1b4a7e8c5d2'
gunicorn -c gunicorn_conf.py run:app -D
echo "✅ 应用已启动"
