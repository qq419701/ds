"""阿奇索开放平台接口服务。

实现阿奇索开放平台的API调用，用于京东订单自动发货。
参考阿奇索开放平台接口文档：https://open.agiso.com/document/#/aldsJd/guide

接入流程：
1. 在阿奇索开放平台创建应用，获取AppID和AppSecret
   入口：https://open.agiso.com/#/my/application/app-list
2. 商家在授权页面授权，将AccessToken发给开发者
   入口：https://aldsJd.agiso.com/#/open/authorize
3. 使用AccessToken调用接口

认证方式：
- HTTP Header: Authorization: Bearer {access_token}
- HTTP Header: ApiVersion: 1
- 公共参数：timestamp（Unix时间戳，秒），sign

签名算法：
- 将所有请求参数按参数名ASCII升序排列，拼接为 key1value1key2value2...
- 在拼接字符串前后各加上AppSecret
- 对整个字符串做MD5摘要（小写32位）
- 即：MD5(AppSecret + key1value1key2value2... + AppSecret)

API基础地址：https://gw-api.agiso.com

主要接口：
- 游戏点卡直充发货：POST /aldsJd/GameCard/RechargeSend  参数：tid
- 游戏点卡点卡发货：POST /aldsJd/GameCard/CardSend      参数：tid, cardJson
- 通用交易发货：    POST /aldsJd/Vtp/Send               参数：tid
- 通用交易退款：    POST /aldsJd/Vtp/Refund             参数：tid
- 查询余额：        POST /open/Bankroll/QueryDeposit    无额外参数

响应格式：{"IsSuccess": true/false, "Error_Code": 0, "Error_Msg": "", "Data": ...}
"""
import hashlib
import json
import logging
import time
import requests

logger = logging.getLogger(__name__)

AGISO_BASE_URL = 'https://gw-api.agiso.com'


def generate_agiso_sign(params, app_secret):
    """生成阿奇索开放平台API签名。

    签名规则：
    1. 将所有请求参数按参数名ASCII升序排列
    2. 拼接为 key1value1key2value2... 格式（不含sign参数）
    3. 在拼接字符串前后各加上AppSecret
    4. 对整个字符串做MD5摘要（小写32位）

    Args:
        params: 请求参数字典（不含sign）
        app_secret: 应用密钥

    Returns:
        str: MD5签名（小写）
    """
    sorted_keys = sorted(params.keys())
    param_str = ''.join(f'{k}{params[k]}' for k in sorted_keys if params[k] is not None)
    sign_str = f'{app_secret}{param_str}{app_secret}'
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest().lower()


def _build_agiso_base_url(shop):
    """构建阿奇索API基础URL（默认使用官方地址，支持自定义覆盖）。"""
    host = shop.agiso_host
    if not host or host in ('open.agiso.com', 'gw-api.agiso.com'):
        return AGISO_BASE_URL
    port = shop.agiso_port
    if port and port not in (80, 443):
        return f'https://{host}:{port}'
    return f'https://{host}'


def _build_headers(shop):
    """构建阿奇索API请求头。"""
    headers = {
        'Content-Type': 'application/json',
        'ApiVersion': '1',
    }
    if shop.agiso_access_token:
        headers['Authorization'] = f'Bearer {shop.agiso_access_token}'
    return headers


def _build_common_params(shop):
    """构建包含公共参数（timestamp、appId）的基础参数字典。"""
    return {
        'appId': shop.agiso_app_id,
        'timestamp': str(int(time.time())),
    }


def _post_agiso(shop, path, params):
    """向阿奇索API发送POST请求（内部）。

    Args:
        shop: 店铺对象
        path: API路径（如 /aldsJd/GameCard/RechargeSend）
        params: 请求参数字典（不含sign，会自动添加）

    Returns:
        dict: 解析后的JSON响应
    """
    params['sign'] = generate_agiso_sign(params, shop.agiso_app_secret)
    url = f'{_build_agiso_base_url(shop)}{path}'
    headers = _build_headers(shop)
    resp = requests.post(url, json=params, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _check_agiso_response(result):
    """解析阿奇索响应，返回 (is_success, error_msg, data)。"""
    if result.get('IsSuccess') is True or result.get('Error_Code') == 0:
        return True, '', result.get('Data')
    error_msg = result.get('Error_Msg') or result.get('message') or '请求失败'
    error_code = result.get('Error_Code', '')
    return False, f'[{error_code}]{error_msg}', None


def agiso_game_direct_deliver(shop, order):
    """游戏点卡直充订单发货。

    调用接口：POST /aldsJd/GameCard/RechargeSend
    参数：tid（京东订单号）

    Returns:
        (bool, str, any): (是否成功, 消息, 返回数据)
    """
    params = _build_common_params(shop)
    params['tid'] = str(order.jd_order_no)
    result = _post_agiso(shop, '/aldsJd/GameCard/RechargeSend', params)
    ok, msg, data = _check_agiso_response(result)
    if ok:
        return True, '游戏直充发货成功', data
    return False, f'游戏直充发货失败：{msg}', None


def agiso_game_card_deliver(shop, order, cards):
    """游戏点卡点卡订单发货。

    调用接口：POST /aldsJd/GameCard/CardSend
    参数：tid（京东订单号），cardJson（卡密JSON字符串）
    卡密格式：[{"cardno":"卡号","cardpass":"卡密"}, ...]

    Returns:
        (bool, str, any): (是否成功, 消息, 返回数据)
    """
    card_list = []
    for card in cards:
        card_no = card.get('cardNo') or card.get('card_no') or card.get('cardNumber') or ''
        card_pass = (card.get('cardPass') or card.get('cardPwd') or
                     card.get('card_pwd') or card.get('password') or '')
        card_list.append({'cardno': card_no, 'cardpass': card_pass})

    params = _build_common_params(shop)
    params['tid'] = str(order.jd_order_no)
    params['cardJson'] = json.dumps(card_list, ensure_ascii=False)
    result = _post_agiso(shop, '/aldsJd/GameCard/CardSend', params)
    ok, msg, data = _check_agiso_response(result)
    if ok:
        return True, '游戏点卡发货成功', data
    return False, f'游戏点卡发货失败：{msg}', None


def agiso_general_deliver(shop, order):
    """通用交易订单发货。

    调用接口：POST /aldsJd/Vtp/Send
    参数：tid（京东订单号）

    Returns:
        (bool, str, any): (是否成功, 消息, 返回数据)
    """
    params = _build_common_params(shop)
    params['tid'] = str(order.jd_order_no)
    result = _post_agiso(shop, '/aldsJd/Vtp/Send', params)
    ok, msg, data = _check_agiso_response(result)
    if ok:
        return True, '通用交易发货成功', data
    return False, f'通用交易发货失败：{msg}', None


def agiso_general_refund(shop, order):
    """通用交易订单退款。

    调用接口：POST /aldsJd/Vtp/Refund
    参数：tid（京东订单号）

    Returns:
        (bool, str, any): (是否成功, 消息, 返回数据)
    """
    params = _build_common_params(shop)
    params['tid'] = str(order.jd_order_no)
    result = _post_agiso(shop, '/aldsJd/Vtp/Refund', params)
    ok, msg, data = _check_agiso_response(result)
    if ok:
        return True, '退款成功', data
    return False, f'退款失败：{msg}', None


def agiso_query_balance(shop):
    """查询阿奇索开放平台余额。

    调用接口：POST /open/Bankroll/QueryDeposit
    无额外业务参数（仅公共参数）

    Returns:
        (bool, str, float|None): (是否成功, 消息, 余额)
    """
    params = _build_common_params(shop)
    try:
        result = _post_agiso(shop, '/open/Bankroll/QueryDeposit', params)
        ok, msg, data = _check_agiso_response(result)
        if ok:
            balance = float(data) if data is not None else 0.0
            return True, f'余额：{balance:.3f}', balance
        return False, f'查询余额失败：{msg}', None
    except Exception as e:
        logger.exception("查询阿奇索余额异常")
        return False, str(e), None


def agiso_auto_deliver(shop, order):
    """根据订单类型和店铺类型调用阿奇索自动发货接口（统一入口）。

    规则：
    - 游戏点卡 + 直充 → RechargeSend
    - 游戏点卡 + 卡密 → CardSend（需已有卡密数据）
    - 通用交易（直充/卡密）→ Vtp/Send

    Args:
        shop: 店铺对象
        order: 订单对象

    Returns:
        (bool, str, dict|None): (是否成功, 消息, 返回数据)
    """
    if not shop.agiso_enabled:
        return False, '未启用阿奇索自动发货', None

    if not shop.agiso_app_id or not shop.agiso_app_secret:
        return False, '阿奇索应用配置不完整', None

    if not shop.agiso_access_token:
        return False, '未配置阿奇索访问令牌', None

    try:
        if shop.shop_type == 1:
            # 游戏点卡平台
            if order.order_type == 1:
                return agiso_game_direct_deliver(shop, order)
            else:
                cards = order.card_info_parsed or []
                return agiso_game_card_deliver(shop, order, cards)
        else:
            # 通用交易平台
            return agiso_general_deliver(shop, order)

    except requests.exceptions.Timeout:
        logger.exception("阿奇索接口调用超时")
        return False, '阿奇索接口调用超时', None
    except requests.exceptions.ConnectionError:
        logger.exception("阿奇索接口连接失败")
        return False, '阿奇索接口连接失败，请检查主机地址配置', None
    except Exception as e:
        logger.exception("阿奇索接口调用异常")
        return False, f'阿奇索接口调用异常：{str(e)}', None


def verify_agiso_push_sign(json_str, timestamp_str, app_secret):
    """验证阿奇索推送消息的签名。

    签名算法：MD5(AppSecret + json + json_value + timestamp + timestamp_value + AppSecret)
    即：在 key=json, key=timestamp 排序后拼接，前后加 AppSecret

    Args:
        json_str: 推送的JSON字符串
        timestamp_str: 推送的时间戳字符串
        app_secret: 应用密钥

    Returns:
        str: 计算得到的签名
    """
    sign_str = f'{app_secret}json{json_str}timestamp{timestamp_str}{app_secret}'
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest().lower()

