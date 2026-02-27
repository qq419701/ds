# DS - 京东虚拟商品订单管理系统

> 游戏点卡 + 通用���易 + 阿奇索自动发货 中间件

## 核心功能

- 🎮 **游戏点卡**：支持直充接单 / 卡密接单，同步/异步回调京东
- 🏪 **通用交易**：支持充值/提取卡密接单，AES加密卡密，回调京东
- 🤖 **阿奇索**：接收阿奇索推送，自动发货完成后回调京东
- 📋 **手动模式**：后台手动操作发货、退款

## 接口地址

| 平台 | 接口 | URL |
|------|------|-----|
| 游戏点卡 | 直充接单 | `POST /api/game/direct` |
| 游戏点卡 | 直充查询 | `POST /api/game/query` |
| 游戏点卡 | 卡密接单 | `POST /api/game/card` |
| 游戏点卡 | 卡密查询 | `POST /api/game/card-query` |
| 通用交易 | 接单 | `POST /api/general/distill` |
| 通用交易 | 反查 | `POST /api/general/query` |
| 阿奇索 | 推送接收 | `POST /api/agiso/push` |

## 快速开始

```bash
git clone https://github.com/qq419701/ds.git
cd ds
pip install -r requirements.txt
python run.py
```

详细部署教程见 [宝塔部署教程.md](宝塔部署教程.md)

技术文档见 [docs/技术文档.md](docs/技术文档.md)