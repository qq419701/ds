"""京东游戏点卡平台接口服务。

实现京东游戏点卡平台的签名验证、订单接收和回调通知功能。
参考京东游戏点卡平台接口文档。

签名规则：key1=value1&key2=value2&...{privatekey}
其中key按ASCII升序排列，直接拼接私钥（无&key=前缀）
"""
import base64
import hashlib
import json
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


def _generate_game_sign_str(params, md5_secret):
    """生成京东游戏点卡签名明文字符串（内部使用）。
    签名明文：key1=value1&key2=value2&...{privatekey}
    """
    filtered = {k: v for k, v in params.items() if k not in ('sign',) and v is not None and str(v) != ''}
    sorted_keys = sorted(filtered.keys())
    sign_str = '&'.join(f'{k}={filtered[k]}' for k in sorted_keys)
    sign_str += "&" + md5_secret  # 按Java示例：最后一个kv后加&再拼私钥
    return sign_str


def verify_game_sign(params, md5_secret):
    """验证京东游戏点卡平台请求的MD5签名。

    签名规则：将所有请求参数（除sign外）按参数名ASCII升序排列，
    拼接为 key1=value1&key2=value2&...{md5_secret} 格式，
    然后对该字符串做MD5摘要（小写）。

    Args:
        params: 请求参数字典
        md5_secret: MD5密钥

    Returns:
        bool: 签名是否有效
    """
    if not md5_secret:
        return True  # 未配置密钥时跳过验签

    received_sign = params.get('sign', '')
    if not received_sign:
        return False

    sign_str = _generate_game_sign_str(params, md5_secret)
    computed_sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest().lower()
    return computed_sign == received_sign.lower()


def generate_game_sign(params, md5_secret):
    """生成京东游戏点卡平台的MD5签名。

    Args:
        params: 请求参数字典（不含sign字段）
        md5_secret: MD5密钥

    Returns:
        str: MD5签名（小写）
    """
    sign_str = _generate_game_sign_str(params, md5_secret)
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest().lower()


def _encode_data(data_obj):
    """将字典编码为京东格式的Base64字符串（UTF-8字符集）。"""
    json_str = json.dumps(data_obj, ensure_ascii=False, separators=(',', ':'))
    return base64.b64encode(json_str.encode('utf-8')).decode('ascii')


def _build_game_callback_params(shop, data_obj):
    """构建游戏点卡平台标准回调参数（含协议参数）。"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    data_b64 = _encode_data(data_obj)

    params = {
        'customerId': shop.game_customer_id or '',
        'timestamp': timestamp,
        'data': data_b64,
    }

    if shop.game_md5_secret:
        sign_params = {k: v for k, v in params.items() if v is not None and str(v) != ''}
        params['sign'] = generate_game_sign(sign_params, shop.game_md5_secret)

    return params


def _normalize_cards_for_jd(cards):
    """将内部卡密格式标准化为京东游戏点卡 cardInfos 格式。

    内部格式：[{'cardNo': 'xxx', 'cardPwd': 'xxx'}, ...]
    或：[{'card_no': 'xxx', 'card_pwd': 'xxx'}, ...]
    京东格式：[{'cardNo': 'xxx', 'cardPass': 'xxx'}, ...]
    """
    result = []
    for card in cards:
        card_no = card.get('cardNo') or card.get('card_no') or ''
        card_pass = card.get('cardPass') or card.get('cardPwd') or card.get('card_pwd') or ''
        result.append({'cardno': card_no, 'cardpass': card_pass})
    return result


def callback_game_direct_success(shop, order):
    """向京东游戏点卡平台回调直充成功通知。

    当未配置回调地址时，视为已回调成功（手动操作场景）。

    Args:
        shop: 店铺对象
        order: 订单对象

    Returns:
        (bool, str): (是否成功, 消息)
    """
    callback_url = shop.game_api_url or shop.game_direct_callback_url
    if not callback_url:
        logger.warning(f"订单 {order.jd_order_no} 未配置游戏直充回调地址，无法回调")
        return False, '未配置回调地址，请在店铺设置中填写游戏直充回调地址'

    data_obj = {
        'orderId': order.jd_order_no,
        'orderStatus': 0,  # 文档：0=充值成功
    }
    params = _build_game_callback_params(shop, data_obj)

    try:
        resp = requests.post(callback_url, data=params, timeout=10)
        result = resp.json()
        ret_code = str(result.get('retCode', ''))
        if ret_code == '100':
            return True, '回调成功'
        return False, f"回调失败: {result.get('retMessage', ret_code)}"
    except Exception as e:
        logger.exception("游戏点卡直充回调失败")
        return False, str(e)


def callback_game_card_deliver(shop, order, cards):
    """向京东游戏点卡平台回调卡密发货信息。

    根据文档，data字段业务参数：
    {
      "orderId": "京东订单号",
      "orderStatus": "0",
      "cardInfos": [{"cardNo": "卡号", "cardPass": "卡密"}]
    }

    Args:
        shop: 店铺对象
        order: 订单对象
        cards: 卡密列表

    Returns:
        (bool, str): (是否成功, 消息)
    """
    callback_url = shop.game_api_url or shop.game_card_callback_url
    if not callback_url:
        logger.warning(f"订单 {order.jd_order_no} 未配置游戏点卡回调地址，无法回调")
        return False, '未配置回调地址，请在店铺设置中填写游戏点卡回调地址'

    jd_cards = _normalize_cards_for_jd(cards)

    data_obj = {
        'orderId': order.jd_order_no,
        'orderStatus': 0,
        'cardinfos': jd_cards,
    }

    params = _build_game_callback_params(shop, data_obj)

    try:
        resp = requests.post(callback_url, data=params, timeout=10)
        result = resp.json()
        ret_code = str(result.get('retCode', ''))
        if ret_code == '100':
            return True, '卡密回调成功'
        return False, f"卡密回调失败: [{ret_code}]{result.get('retMessage', '')}"
    except Exception as e:
        logger.exception("游戏点卡卡密回调失败")
        return False, str(e)


def callback_game_refund(shop, order):
    """向京东游戏点卡平台回调退款通知。

    orderStatus=2 表示履约失败（触发退款）

    Args:
        shop: 店铺对象
        order: 订单对象

    Returns:
        (bool, str): (是否成功, 消息)
    """
    # 根据订单类型选择正确的回调URL
    # order_type=1 直充用 game_direct_callback_url (gameApi.action)
    # order_type=2 卡密用 game_card_callback_url   (cardApi.action)
    if getattr(order, 'order_type', 1) == 2:
        callback_url = shop.game_card_callback_url or shop.game_api_url or shop.game_direct_callback_url
    else:
        callback_url = shop.game_direct_callback_url or shop.game_api_url or shop.game_card_callback_url
    if not callback_url:
        logger.warning(f"订单 {order.jd_order_no} 未配置游戏回调地址，无法回调")
        return False, '未配置回调地址，请在店铺设置中填写游戏点卡回调地址'

    data_obj = {
        'orderId': order.jd_order_no,
        'orderStatus': 2,  # 2=履约失败/退款
    }

    params = _build_game_callback_params(shop, data_obj)

    try:
        resp = requests.post(callback_url, data=params, timeout=10)
        result = resp.json()
        ret_code = str(result.get('retCode', ''))
        if ret_code == '100':
            return True, '退款回调成功'
        return False, f"退款回调失败: [{ret_code}]{result.get('retMessage', '')}"
    except Exception as e:
        logger.exception("游戏点卡退款回调失败")
        return False, str(e)
