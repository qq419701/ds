#!/bin/bash
cd /www/wwwroot/dianshang
echo "🔄 正在停止应用..."
./stop.sh
sleep 2
echo "🚀 正在启动应用..."
./start.sh
echo "✅ 应用已重启完成"
