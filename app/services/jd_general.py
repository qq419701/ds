"""京东通用交易平台接口服务。

实现京东通用交易平台的签名验证、订单接收和回调通知功能。
参考京东通用交易平台接口文档。

签名规则（通用交易）：key1value1key2value2...PRIVATEKEY
key 按字母升序，value 直接拼接（无=无&），最后拼 PRIVATEKEY
"""
import base64
import hashlib
import json
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def _aes_encrypt(data: str, key: str) -> str:
    """AES-256-ECB 加密，结果 base64 编码。"""
    if not HAS_CRYPTO:
        return data
    try:
        key_bytes = key.encode('utf-8')[:32].ljust(32, b'\0')
        # ECB mode is required by JD General Trading Platform API spec (加密模式：ECB)
        # This is a platform requirement and cannot be changed for compatibility reasons.
        cipher = AES.new(key_bytes, AES.MODE_ECB)  # noqa: S305 - required by JD API spec
        encrypted = cipher.encrypt(pad(data.encode('utf-8'), AES.block_size))
        return base64.b64encode(encrypted).decode('ascii')
    except Exception as e:
        logger.warning(f"AES加密失败: {e}")
        return data


def _generate_general_sign_str(params, md5_secret):
    """生成通用交易平台签名明文。
    规则：key1value1key2value2...PRIVATEKEY（key按字母升序，无=无&）
    """
    filtered = {k: v for k, v in params.items()
                if k not in ('sign', 'signType') and v is not None and str(v) != ''}
    sorted_keys = sorted(filtered.keys())
    sign_str = ''.join(f'{k}{filtered[k]}' for k in sorted_keys)
    sign_str += md5_secret
    return sign_str


def verify_general_sign(params, md5_secret):
    """验证京东通用交易平台请求的MD5签名。

    签名规则：将所有请求参数（除sign、signType外）按参数名字母升序排列，
    拼接为 key1value1key2value2...PRIVATEKEY 格式（无=无&），
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

    sign_str = _generate_general_sign_str(params, md5_secret)
    computed_sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest().lower()
    return computed_sign == received_sign.lower()


def generate_general_sign(params, md5_secret):
    """生成京东通用交易平台的MD5签名。

    Args:
        params: 请求参数字典（不含sign字段）
        md5_secret: MD5密钥

    Returns:
        str: MD5签名（小写）
    """
    sign_str = _generate_general_sign_str(params, md5_secret)
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest().lower()


def _normalize_cards_for_general(cards):
    """将内部卡密格式标准化为通用交易 product 格式。"""
    result = []
    for card in cards:
        card_number = card.get('cardNumber') or card.get('cardNo') or card.get('card_no') or ''
        password = (card.get('password') or card.get('cardPass') or
                    card.get('cardPwd') or card.get('card_pwd') or '')
        result.append({
            'cardNumber': card_number,
            'password': password,
            'expiryDate': card.get('expiryDate', '2099-12-31'),
        })
    return result


def _build_general_callback_params(shop, order, produce_status, product_json=None):
    """构建通用交易平台标准回调参数。"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    params = {
        'vendorId': str(shop.general_vendor_id or ''),
        'jdOrderNo': str(order.jd_order_no),
        'agentOrderNo': str(order.order_no),
        'produceStatus': str(produce_status),
        'quantity': str(order.quantity or 1),
        'timestamp': timestamp,
        'signType': 'MD5',
    }

    if product_json:
        if shop.general_aes_secret:
            params['product'] = _aes_encrypt(product_json, shop.general_aes_secret)
        else:
            params['product'] = product_json

    if shop.general_md5_secret:
        sign_params = {k: v for k, v in params.items()
                       if k not in ('sign', 'signType') and v is not None and str(v) != ''}
        params['sign'] = generate_general_sign(sign_params, shop.general_md5_secret)

    return params


def callback_general_success(shop, order):
    """向京东通用交易平台回调充值成功通知。

    Args:
        shop: 店铺对象
        order: 订单对象

    Returns:
        (bool, str): (是否成功, 消息)
    """
    callback_url = getattr(order, 'notify_url', None) or shop.general_callback_url
    if not callback_url:
        logger.warning(f"订单 {order.jd_order_no} 未配置通用交易回调地址，无法回调")
        return False, '未配置回调地址，请在店铺设置中填写通用交易回调地址'

    if not callback_url.endswith('/produce/result'):
        callback_url = callback_url.rstrip('/') + '/produce/result'

    params = _build_general_callback_params(shop, order, produce_status=1)

    try:
        resp = requests.post(callback_url, data=params, timeout=10)
        result = resp.json()
        code = str(result.get('code', ''))
        if code == '0':
            return True, '回调成功'
        return False, f"回调失败: [{code}]{result.get('message', '')}"
    except Exception as e:
        logger.exception("通用交易充值成功回调失败")
        return False, str(e)


def callback_general_card_deliver(shop, order, cards):
    """向京东通用交易平台回调卡密发货信息。

    product 字段为 AES 加密后的卡密数组 JSON：
    [{"cardNumber":"","password":"","expiryDate":"yyyy-MM-dd"}]

    Args:
        shop: 店铺对象
        order: 订单对象
        cards: 卡密列表

    Returns:
        (bool, str): (是否成功, 消息)
    """
    callback_url = getattr(order, 'notify_url', None) or shop.general_callback_url
    if not callback_url:
        logger.warning(f"订单 {order.jd_order_no} 未配置通用交易回调地址，无法回调")
        return False, '未配置回调地址，请在店铺设置中填写通用交易回调地址'

    if not callback_url.endswith('/produce/result'):
        callback_url = callback_url.rstrip('/') + '/produce/result'

    jd_cards = _normalize_cards_for_general(cards)
    product_json = json.dumps(jd_cards, ensure_ascii=False)

    params = _build_general_callback_params(shop, order, produce_status=1, product_json=product_json)

    try:
        resp = requests.post(callback_url, data=params, timeout=10)
        result = resp.json()
        code = str(result.get('code', ''))
        if code == '0':
            return True, '卡密回调成功'
        return False, f"卡密回调失败: [{code}]{result.get('message', '')}"
    except Exception as e:
        logger.exception("通用交易卡密回调失败")
        return False, str(e)


def callback_general_refund(shop, order):
    """向京东通用交易平台回调退款通知（produceStatus=2 失败触发退款）。

    Args:
        shop: 店铺对象
        order: 订单对象

    Returns:
        (bool, str): (是否成功, 消息)
    """
    callback_url = getattr(order, 'notify_url', None) or shop.general_callback_url
    if not callback_url:
        logger.warning(f"订单 {order.jd_order_no} 未配置通用交易回调地址，无法回调")
        return False, '未配置回调地址，请在店铺设置中填写通用交易回调地址'

    if not callback_url.endswith('/produce/result'):
        callback_url = callback_url.rstrip('/') + '/produce/result'

    params = _build_general_callback_params(shop, order, produce_status=2)

    try:
        resp = requests.post(callback_url, data=params, timeout=10)
        result = resp.json()
        code = str(result.get('code', ''))
        if code == '0':
            return True, '退款回调成功'
        return False, f"退款回调失败: [{code}]{result.get('message', '')}"
    except Exception as e:
        logger.exception("通用交易退款回调失败")
        return False, str(e)
