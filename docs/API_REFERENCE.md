# 京东对接接口文档

## 一、系统架构

```
dianshang/
├── app/
│   ├── __init__.py              # Flask应用工厂，含API日志中间件
│   ├── models/
│   │   ├── shop.py              # 店铺模型
│   │   ├── order.py             # 订单模型
│   │   └── api_log.py           # API日志模型
│   ├── routes/
│   │   ├── jd_game_api.py       # 游戏点卡平台接口（/api/game/*）
│   │   └── jd_general_api.py    # 通用交易平台接口（/api/general/*）
│   └── services/
│       ├── jd_game.py           # 游戏点卡签名/回调服务
│       └── jd_general.py        # 通用交易签名/回调服务
└── docs/
    └── API_REFERENCE.md         # 本文件
```

---

## 二、游戏点卡平台

### 2.1 通信规范

**请求格式：** `application/x-www-form-urlencoded`

```
customerId=xxx&data=base64(JSON)&sign=xxx&timestamp=xxx
```

**data字段：** 使用 GBK 字符集对 JSON 字符串进行 Base64 编码。

解码示例（Python）：
```python
import base64, json
decoded = base64.b64decode(data_b64).decode('gbk')
biz = json.loads(decoded)
```

编码示例（Python）：
```python
import base64, json
encoded = base64.b64encode(json.dumps(obj, ensure_ascii=False).encode('gbk')).decode('ascii')
```

**签名算法：**

1. 过滤掉 `sign` 字段，其余参数按参数名 ASCII 升序排列
2. 拼接为 `key1=value1&key2=value2&...&key=md5_secret` 格式
3. 对该字符串做 MD5 摘要（小写十六进制）

```python
import hashlib
filtered = {k: v for k, v in params.items() if k != 'sign' and v}
sorted_keys = sorted(filtered.keys())
sign_str = '&'.join(f'{k}={filtered[k]}' for k in sorted_keys)
sign_str += f'&key={md5_secret}'
sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest().lower()
```

> **注意：** 签名使用**外层参数**（`customerId`、`data`、`timestamp`），而非 data 解码后的业务字段。

---

### 2.2 接口列表

#### 2.2.1 直充接单

- **URL：** `POST /api/game/direct`
- **京东推送格式：** `customerId=xxx&data=base64(JSON)&sign=xxx&timestamp=xxx`
- **data 解码后字段：**

| 字段          | 类型   | 说明         |
|---------------|--------|--------------|
| orderId       | string | 京东订单号   |
| skuId         | string | 商品SKU ID   |
| brandId       | string | 品牌ID       |
| totalPrice    | string | 订单金额（元）|
| buyNum        | string | 购买数量     |
| gameAccount   | string | 充值账号     |

- **返回格式：**

```json
{"retCode": "100", "retMessage": "接收成功"}
```

| retCode | 说明     |
|---------|----------|
| 100     | 接收成功 |
| 200     | 接收失败 |

---

#### 2.2.2 直充查询

- **URL：** `POST /api/game/query` 或 `GET /api/game/query`
- **请求参数：**

| 参数      | 说明       |
|-----------|------------|
| orderId   | 京东订单号 |

- **返回格式：**

```json
{
  "success": true,
  "code": 0,
  "data": {
    "orderId": "本地订单号",
    "jdOrderId": "京东订单号",
    "status": "SUCCESS",
    "orderStatus": 2,
    "message": "已完成"
  }
}
```

---

#### 2.2.3 卡密接单

- **URL：** `POST /api/game/card`
- **请求格式：** 同直充接单（`customerId=xxx&data=base64(JSON)&sign=xxx&timestamp=xxx`）
- **data 解码后字段：** 同直充接单（无 `gameAccount` 字段）
- **返回格式：** 同直充接单

---

#### 2.2.4 卡密查询

- **URL：** `POST /api/game/card-query` 或 `GET /api/game/card-query`
- **请求格式：** `customerId=xxx&data=base64({"orderId":"xxx"})&timestamp=xxx&sign=xxx`
- **返回格式：**

```json
{
  "retCode": "100",
  "retMessage": "查询成功",
  "data": "base64编码的JSON字符串"
}
```

data 解码后内容：

```json
{
  "orderStatus": 0,
  "cards": [{"cardNo": "xxx", "cardPwd": "xxx"}]
}
```

| orderStatus | 说明         |
|-------------|--------------|
| 0           | 发货成功     |
| 1           | 处理中/待发货|
| 2           | 退款/失败    |

---

### 2.3 主动回调京东

#### 2.3.1 直充成功通知

- **URL：** `POST https://card.jd.com/api/gameApi.action`
- **请求体：** `customerId=xxx&data=base64(JSON)&sign=xxx&timestamp=xxx`
- **data 内容（成功）：**

```json
{"orderId": "京东订单号", "orderStatus": "0"}
```

- **data 内容（退款）：**

```json
{"orderId": "京东订单号", "orderStatus": "2", "failedCode": 999, "failedReason": "商家退款"}
```

#### 2.3.2 卡密发货通知

- **URL：** `POST https://card.jd.com/api/cardApi.action`
- **请求体：** `customerId=xxx&data=base64(JSON)&sign=xxx&timestamp=xxx`
- **data 内容：**

```json
{
  "orderId": "京东订单号",
  "orderStatus": "0",
  "cards": [{"cardNo": "卡号", "cardPwd": "卡密"}]
}
```

---

## 三、通用交易平台

### 3.1 通信规范

**请求格式：** `application/x-www-form-urlencoded` 或 JSON

**签名算法（与游戏点卡不同！）：**

1. 过滤掉 `sign` 字段，其余参数按参数名 ASCII 升序排列
2. 拼接为 `key1value1key2value2...PRIVATEKEY` 格式（**无 `=` 无 `&`**）
3. 对该字符串做 MD5 摘要（小写十六进制）

```python
import hashlib
filtered = {k: v for k, v in params.items() if k != 'sign' and v}
sorted_keys = sorted(filtered.keys())
sign_str = ''.join(f'{k}{filtered[k]}' for k in sorted_keys)
sign_str += md5_secret
sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest().lower()
```

> ⚠️ **两种签名算法不能混用！** 游戏点卡用 `key=value&` 格式，通用交易用 `keyvalue` 格式。

---

### 3.2 接口列表

#### 3.2.1 接单（distill）

- **URL：** `POST /api/general/distill`

#### 3.2.2 查询（query）

- **URL：** `POST /api/general/query` 或 `GET /api/general/query`

---

### 3.3 主动回调

- **回调地址：** `notifyUrl` 参数指定的地址 + `/produce/result`
- **卡密加密：** 使用 AES-256 ECB 模式加密，密钥为配置的 `general_aes_key`

---

## 四、店铺配置说明（shops 表字段）

| 字段                    | 说明                                 |
|-------------------------|--------------------------------------|
| shop_type               | 1=游戏点卡，2=通用交易               |
| is_enabled              | 1=启用，0=禁用                       |
| game_customer_id        | 京东游戏平台 customerId（用于匹配店铺）|
| game_md5_secret         | 京东游戏平台 MD5 签名密钥            |
| game_direct_callback_url| 直充回调地址                         |
| game_card_callback_url  | 卡密回调地址                         |
| general_md5_secret      | 通用交易平台 MD5 签名密钥            |
| general_aes_key         | 通用交易平台 AES 加密密钥            |
| expire_time             | 店铺到期时间（NULL=永不过期）        |
| auto_deliver            | 1=自动发货，0=手动                   |
| notify_enabled          | 1=开启钉钉通知，0=关闭               |

---

## 五、订单状态说明

### 本地状态码

| 状态码 | 说明     |
|--------|----------|
| 0      | 待支付   |
| 1      | 处理中   |
| 2      | 已完成   |
| 3      | 已取消   |
| 4      | 已退款   |
| 5      | 异常     |

### 本地状态 → 京东卡密状态映射

| 本地状态 | 京东状态（orderStatus）| 说明         |
|----------|------------------------|--------------|
| 0        | 1                      | 处理中       |
| 1        | 1                      | 处理中       |
| 2        | 0                      | 发货成功     |
| 3        | 2                      | 退款         |
| 4        | 2                      | 退款         |
| 5        | 2                      | 异常退款     |

---

## 六、踩坑记录（重要！）

### 6.1 `request.get_json()` 导致 415 错误

**问题：** 京东推单使用 `application/x-www-form-urlencoded` 格式，`request.get_json()` 会抛出 415 异常。

**修复：** 始终先尝试 `request.form.to_dict()`，再回退到 JSON：

```python
raw = request.form.to_dict() or request.get_json(silent=True) or {}
```

---

### 6.2 京东推单 data 字段是 Base64 编码的

**问题：** 代码直接从 form 取 `orderId`，但实际业务数据在 base64 编码的 `data` 字段里。

**修复：** 收到请求后先解码 `data` 字段，再从解码结果中取业务字段：

```python
data_b64 = raw.get('data', '')
if data_b64:
    biz = decode_data(data_b64)  # 解码GBK Base64
else:
    biz = raw
jd_order_no = str(biz.get('orderId') or biz.get('jdOrderId') or '')
```

---

### 6.3 Base64 编码用 GBK 字符集

京东的 `data` 字段使用 **GBK** 字符集编码，不是 UTF-8。解码时需先尝试 GBK，失败后回退到 UTF-8：

```python
decoded_str = base64.b64decode(data_b64).decode('gbk')
```

---

### 6.4 签名中 sign 字段不参与计算

生成/验证签名时，必须从参数中排除 `sign` 字段本身，否则签名值每次都不同。

---

### 6.5 回调地址规则

- **游戏点卡直充回调：** 固定地址 `https://card.jd.com/api/gameApi.action`
- **游戏点卡卡密回调：** 固定地址 `https://card.jd.com/api/cardApi.action`
- **通用交易回调：** 使用接单时京东传入的 `notifyUrl` + `/produce/result`

---

### 6.6 回调使用 POST form 表单格式

向京东回调时，使用 `application/x-www-form-urlencoded` 格式（POST form），而非 JSON。

---

### 6.7 两种签名算法不能混用

| 平台       | 签名格式                          |
|------------|-----------------------------------|
| 游戏点卡   | `key1=value1&key2=value2&key=密钥`|
| 通用交易   | `key1value1key2value2密钥`        |

---

### 6.8 京东查询接口可能不带 Base64

部分查询请求可能直接传 `orderId` 字段而不使用 `data` base64 编码，需要兼容两种格式：

```python
data_b64 = params.get('data', '')
if data_b64:
    biz_data = decode_data(data_b64)
    jd_order_no = str(biz_data.get('orderId', ''))
else:
    jd_order_no = str(params.get('orderId') or params.get('jdOrderId') or '')
```

---

### 6.9 API 日志记录需要中间件

API 日志模型（`ApiLog`）和展示页面已存在，但日志页面为空，原因是没有中间件记录请求。

**修复：** 在 `create_app()` 中注册 `@app.after_request` 钩子，自动记录所有 `/api/` 前缀的请求（排除高频轮询的 `new-order-count`）。

---

## 七、接口 URL 汇总

| 接口         | 方法       | URL                      |
|--------------|------------|--------------------------|
| 游戏直充接单 | POST       | `/api/game/direct`       |
| 游戏直充查询 | POST / GET | `/api/game/query`        |
| 游戏卡密接单 | POST       | `/api/game/card`         |
| 游戏卡密查询 | POST / GET | `/api/game/card-query`   |
| 通用交易接单 | POST       | `/api/general/distill`   |
| 通用交易查询 | POST / GET | `/api/general/query`     |

---

## 八、调试方法

### curl 测试示例

**直充接单（模拟京东推单）：**

```bash
# 构造 base64 data 字段（GBK编码）
python3 -c "
import base64, json
biz = {'orderId':'TEST001','skuId':'12345','totalPrice':'1.00','buyNum':'1','gameAccount':'user123'}
data = base64.b64encode(json.dumps(biz,ensure_ascii=False).encode('gbk')).decode()
print(data)
"

# 发送请求
curl -X POST http://localhost:5000/api/game/direct \
  -d "customerId=YOUR_CUSTOMER_ID&data=BASE64_DATA&timestamp=1234567890&sign=YOUR_SIGN"
```

**卡密查询：**

```bash
curl -X POST http://localhost:5000/api/game/card-query \
  -d "orderId=JD_ORDER_NO"
```

### 查看日志

```bash
tail -f /var/log/app.log
```

### 数据库查询

```sql
-- 查看最近 API 日志
SELECT * FROM api_logs ORDER BY create_time DESC LIMIT 20;

-- 查看待处理订单
SELECT * FROM orders WHERE order_status = 0 ORDER BY create_time DESC;
```
