#!/bin/bash
cd /www/wwwroot/ds
echo "🔄 正在停止应用..."
bash stop.sh
sleep 2
echo "🚀 正在启动应用..."
bash start.sh
echo "✅ 应用已重启完成"
