"""91卡券开放平台接口服务。

实现91卡券开放平台的API调用，用于卡密订单的自动提卡和发货。
91卡券平台支持：
- 卡种列表查询（获取仓库中所有卡种）
- 提卡（从仓库取出指定数量的卡密）
- 添加卡密/卡券方案
- 更新卡券方案

接入流程：
1. 在店铺配置页面填写91卡券API密钥和签名密钥
2. 在商品管理页面为每个SKU配置对应的卡种ID
3. 系统收到京东订单后，根据SKU匹配卡种，自动提卡发货

API认证方式：
- 请求头：X-Api-Key: {api_key}
- 签名：HMAC-SHA256 或 MD5（根据平台要求）

注意：
- 91卡券对应卡密订单类型（order_type=2）
- 直充订单类型（order_type=1）由直充API处理（预留）
- 所有时间均使用北京时间（UTC+8）
"""
import hashlib
import hmac
import json
import logging
import time
import requests

logger = logging.getLogger(__name__)

# 91卡券默认API基础地址
CARD91_DEFAULT_BASE_URL = 'https://api.91kaquan.com'

# 请求超时时间（秒）
REQUEST_TIMEOUT = 30


def _get_base_url(shop):
    """获取API基础地址（优先使用店铺自定义地址）。"""
    if shop and shop.card91_api_url:
        return shop.card91_api_url.rstrip('/')
    return CARD91_DEFAULT_BASE_URL


def _build_sign(params, api_secret):
    """生成API签名。

    签名规则：
    1. 按参数名ASCII升序排列
    2. 拼接为 key1=value1&key2=value2 格式
    3. 加上 &secret={api_secret}
    4. 对整个字符串做MD5摘要（小写32位）
    """
    if not api_secret:
        return ''
    # 排除sign参数本身
    sorted_params = sorted(
        [(k, str(v)) for k, v in params.items() if k != 'sign' and v is not None],
        key=lambda x: x[0]
    )
    query_str = '&'.join(f'{k}={v}' for k, v in sorted_params)
    query_str += f'&secret={api_secret}'
    return hashlib.md5(query_str.encode('utf-8')).hexdigest().lower()


def _do_request(shop, method, endpoint, params=None):
    """发送91卡券API请求。

    Args:
        shop: 店铺对象（包含API配置）
        method: HTTP方法（GET/POST）
        endpoint: API路径（如 /api/card/types）
        params: 请求参数字典

    Returns:
        (success: bool, message: str, data: dict|list|None)
    """
    if not shop or not shop.card91_api_key:
        return False, '91卡券API密钥未配置', None

    base_url = _get_base_url(shop)
    url = f'{base_url}{endpoint}'

    # 构建公共参数
    req_params = {
        'api_key': shop.card91_api_key,
        'timestamp': str(int(time.time())),
    }
    if params:
        req_params.update(params)

    # 生成签名
    if shop.card91_api_secret:
        req_params['sign'] = _build_sign(req_params, shop.card91_api_secret)

    try:
        if method.upper() == 'GET':
            resp = requests.get(url, params=req_params, timeout=REQUEST_TIMEOUT)
        else:
            resp = requests.post(url, json=req_params, timeout=REQUEST_TIMEOUT)

        resp.raise_for_status()
        result = resp.json()

        logger.debug(f'91卡券API响应 [{endpoint}]: {json.dumps(result, ensure_ascii=False)[:500]}')

        # 处理响应（兼容多种响应格式）
        code = result.get('code', result.get('status', 0))
        msg = result.get('msg', result.get('message', ''))
        data = result.get('data', result.get('result', None))

        if code in (0, 200, '0', '200', True, 'success'):
            return True, msg or '成功', data
        else:
            logger.warning(f'91卡券API错误 [{endpoint}]: code={code}, msg={msg}')
            return False, msg or f'接口返回错误码：{code}', data

    except requests.exceptions.ConnectionError as e:
        logger.error(f'91卡券API连接失败 [{endpoint}]: {e}')
        return False, f'连接91卡券服务器失败，请检查API地址配置', None
    except requests.exceptions.Timeout:
        logger.error(f'91卡券API超时 [{endpoint}]')
        return False, '请求91卡券服务器超时', None
    except requests.exceptions.HTTPError as e:
        logger.error(f'91卡券API HTTP错误 [{endpoint}]: {e}')
        return False, f'HTTP请求错误：{e}', None
    except Exception as e:
        logger.error(f'91卡券API异常 [{endpoint}]: {e}')
        return False, f'请求异常：{str(e)}', None


def card91_get_card_types(shop):
    """获取91卡券卡种列表。

    返回当前API账号下所有可用的卡种信息，供商品配置时选择。

    Args:
        shop: 店铺对象

    Returns:
        (success: bool, message: str, card_types: list)
        card_types 格式：[{'id': '卡种ID', 'name': '卡种名称', 'stock': 库存数量, ...}]
    """
    ok, msg, data = _do_request(shop, 'GET', '/api/card/types')
    if ok and data:
        # 标准化返回格式
        card_types = []
        items = data if isinstance(data, list) else data.get('list', data.get('items', []))
        for item in items:
            card_types.append({
                'id': str(item.get('id', item.get('type_id', ''))),
                'name': item.get('name', item.get('type_name', '')),
                'stock': item.get('stock', item.get('count', 0)),
                'price': item.get('price', 0),
                'remark': item.get('remark', item.get('desc', '')),
            })
        return True, msg, card_types
    return ok, msg, []


def card91_fetch_cards(shop, card_type_id, quantity, order_no):
    """从91卡券仓库提取卡密。

    根据卡种ID和数量，从91卡券仓库中取出卡密，用于订单发货。

    Args:
        shop: 店铺对象
        card_type_id: 卡种ID（在商品配置中设置）
        quantity: 需要提取的数量
        order_no: 系统订单号（用于防重复提卡）

    Returns:
        (success: bool, message: str, cards: list)
        cards 格式：[{'cardNo': '卡号', 'cardPwd': '密码', 'expiry': '有效期'}, ...]
    """
    if not card_type_id:
        return False, '卡种ID未配置', []

    params = {
        'card_type_id': str(card_type_id),
        'quantity': int(quantity),
        'order_no': str(order_no),
    }
    ok, msg, data = _do_request(shop, 'POST', '/api/card/fetch', params)
    if ok and data:
        cards = []
        items = data if isinstance(data, list) else data.get('cards', data.get('list', []))
        for item in items:
            cards.append({
                'cardNo': str(item.get('card_no', item.get('cardNo', item.get('number', '')))),
                'cardPwd': str(item.get('card_pwd', item.get('cardPwd', item.get('password', '')))),
                'expiry': str(item.get('expiry', item.get('expire', ''))),
            })
        if cards:
            return True, f'成功提取{len(cards)}张卡密', cards
        else:
            return False, '提卡成功但未返回卡密数据', []
    return ok, msg, []


def card91_add_card_plan(shop, plan_name, card_type_id, params=None):
    """添加卡密卡券方案。

    在91卡券平台创建一个新的卡券方案，方便批量管理。

    Args:
        shop: 店铺对象
        plan_name: 方案名称
        card_type_id: 卡种ID
        params: 额外参数

    Returns:
        (success: bool, message: str, plan_id: str|None)
    """
    req_params = {
        'plan_name': plan_name,
        'card_type_id': str(card_type_id),
    }
    if params:
        req_params.update(params)

    ok, msg, data = _do_request(shop, 'POST', '/api/plan/add', req_params)
    if ok and data:
        plan_id = str(data.get('plan_id', data.get('id', '')))
        return True, msg, plan_id
    return ok, msg, None


def card91_update_card_plan(shop, plan_id, params=None):
    """更新卡券方案。

    Args:
        shop: 店铺对象
        plan_id: 方案ID
        params: 要更新的参数

    Returns:
        (success: bool, message: str, data: dict|None)
    """
    req_params = {'plan_id': str(plan_id)}
    if params:
        req_params.update(params)

    return _do_request(shop, 'POST', '/api/plan/update', req_params)


def card91_get_stock(shop, card_type_id):
    """查询指定卡种库存数量。

    Args:
        shop: 店铺对象
        card_type_id: 卡种ID

    Returns:
        (success: bool, message: str, stock: int)
    """
    ok, msg, data = _do_request(shop, 'GET', '/api/card/stock',
                                  {'card_type_id': str(card_type_id)})
    if ok and data:
        stock = int(data.get('stock', data.get('count', 0)))
        return True, f'库存：{stock}张', stock
    return ok, msg, 0


def card91_test_connection(shop):
    """测试91卡券API连接是否正常。

    通过调用卡种列表接口验证配置是否正确。

    Args:
        shop: 店铺对象

    Returns:
        (success: bool, message: str)
    """
    ok, msg, data = _do_request(shop, 'GET', '/api/card/types')
    if ok:
        count = len(data) if isinstance(data, list) else 0
        return True, f'连接成功，共有{count}个卡种'
    return False, msg


def card91_auto_deliver(shop, order, product):
    """91卡券自动发卡。

    根据商品配置从91卡券提取卡密，并返回卡密列表。
    调用方负责将卡密保存到订单并回调京东。

    Args:
        shop: 店铺对象
        order: 订单对象
        product: 商品配置对象（包含91卡券卡种ID）

    Returns:
        (success: bool, message: str, cards: list)
    """
    if not product or not product.card91_card_type_id:
        return False, '商品未配置91卡券卡种ID', []

    # 检查店铺91卡券配置
    if not shop or not shop.card91_api_key:
        return False, '店铺未配置91卡券API密钥', []

    logger.info(f'91卡券自动提卡：订单={order.order_no}，'
                f'卡种={product.card91_card_type_id}，数量={order.quantity}')

    ok, msg, cards = card91_fetch_cards(
        shop,
        product.card91_card_type_id,
        order.quantity,
        order.order_no
    )

    if ok and len(cards) >= order.quantity:
        logger.info(f'91卡券提卡成功：订单={order.order_no}，共{len(cards)}张')
        return True, f'成功提取{len(cards)}张卡密', cards[:order.quantity]
    elif ok:
        logger.warning(f'91卡券提卡数量不足：订单={order.order_no}，'
                       f'需要{order.quantity}张，实际{len(cards)}张')
        return False, f'卡密数量不足，需要{order.quantity}张，只取到{len(cards)}张', []
    else:
        logger.error(f'91卡券提卡失败：订单={order.order_no}，原因={msg}')
        return False, f'提卡失败：{msg}', []
