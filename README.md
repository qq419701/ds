# DS - 京东虚拟商品订单管理系统

> 游戏点卡 + 通用交易 + 阿奇索自动发货 中间件

## 核心功能

- 🎮 **游戏点卡**：支持直充接单 / 卡密接单，同步/异步回调京东
- 🏪 **通用交易**：支持充值/提取卡密接单，AES加密卡密，回调京东
- 🤖 **阿奇索**：接收阿奇索推送，自动发货完成后回调京东
- 📋 **手动模式**：后台手动操作发货、退款
- 🔔 **订单通知**：钉钉/企业微信机器人新订单推送
- 📊 **统计报表**：订单数量、金额统计

## 接口地址

### 🎮 游戏点卡接口

| 接口 | URL | 说明 |
|------|-----|------|
| 直充接单 | `POST /api/game/direct` | 接收直充订单 |
| 直充查询 | `POST /api/game/query` | 查询直充订单状态 |
| 卡密接单 | `POST /api/game/card` | 接收卡密订单 |
| 卡密查询 | `POST /api/game/card-query` | 查询卡密订单（含卡密） |

### 🏪 通用交易接口

| 接口 | URL | 说明 |
|------|-----|------|
| 接单 | `POST /api/general/distill` | 接收通用交易订单 |
| 反查 | `POST /api/general/query` | 查询订单状态 |

### 🤖 阿奇索推送

| 接口 | URL | 说明 |
|------|-----|------|
| 推送接收 | `POST /api/agiso/push` | 接收阿奇索发货通知 |

## 快速开始

```bash
git clone https://github.com/qq419701/ds.git
cd ds
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env  # 编辑 .env 填写数据库信息

# 初始化数据库
python migrations/init_db.py

# 启动开发服务
python run.py
```

默认管理员账号：`admin` / `admin123`（首次登录后请立即修改密码）

## 文档

- 详细部署教程：[宝塔部署教程.md](宝塔部署教程.md)
- 技术文档：[docs/技术文档.md](docs/技术文档.md)
- API参考：[docs/API_REFERENCE.md](docs/API_REFERENCE.md)

## 技术栈

- **后端**：Python 3.9+ / Flask
- **数据库**：MySQL 5.7+
- **部署**：Gunicorn + Nginx + Supervisor
