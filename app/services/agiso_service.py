import json
import logging
import requests
from datetime import datetime
from app.utils.sign import agiso_sign

logger = logging.getLogger(__name__)


def get_agiso_headers(shop):
    """获取阿奇索API请求头"""
    return {
        'Authorization': f'Bearer {shop.agiso_access_token}',
        'ApiVersion': '1',
        'Content-Type': 'application/json'
    }


def get_agiso_base_url(shop):
    """获取阿奇索API基础URL"""
    return 'https://gw-api.agiso.com'


def send_game_direct(shop, order):
    """游戏点卡直充发货"""
    timestamp = str(int(datetime.now().timestamp()))
    params = {
        "appId": shop.agiso_app_id,
        "timestamp": timestamp,
        "tid": order.order_id
    }
    params["sign"] = agiso_sign(params, shop.agiso_app_secret)

    url = f"{get_agiso_base_url(shop)}/aldsJd/GameCard/RechargeSend"
    try:
        resp = requests.post(url, json=params, headers=get_agiso_headers(shop), timeout=15)
        result = resp.json()
        logger.info(f"阿奇索直充发货 order_id={order.order_id} result={result}")
        return result
    except Exception as e:
        logger.error(f"阿奇索直充发货失败 order_id={order.order_id} error={e}")
        return None


def send_game_card(shop, order, card_json):
    """游戏点卡发卡密"""
    timestamp = str(int(datetime.now().timestamp()))
    params = {
        "appId": shop.agiso_app_id,
        "timestamp": timestamp,
        "tid": order.order_id,
        "cardJson": card_json
    }
    params["sign"] = agiso_sign(params, shop.agiso_app_secret)

    url = f"{get_agiso_base_url(shop)}/aldsJd/GameCard/CardSend"
    try:
        resp = requests.post(url, json=params, headers=get_agiso_headers(shop), timeout=15)
        result = resp.json()
        logger.info(f"阿奇索卡密发货 order_id={order.order_id} result={result}")
        return result
    except Exception as e:
        logger.error(f"阿奇索卡密发货失败 order_id={order.order_id} error={e}")
        return None


def send_general(shop, order):
    """通用交易发货"""
    timestamp = str(int(datetime.now().timestamp()))
    params = {
        "appId": shop.agiso_app_id,
        "timestamp": timestamp,
        "tid": order.jd_order_no
    }
    params["sign"] = agiso_sign(params, shop.agiso_app_secret)

    url = f"{get_agiso_base_url(shop)}/aldsJd/Vtp/Send"
    try:
        resp = requests.post(url, json=params, headers=get_agiso_headers(shop), timeout=15)
        result = resp.json()
        logger.info(f"阿奇索通用交易发货 jd_order_no={order.jd_order_no} result={result}")
        return result
    except Exception as e:
        logger.error(f"阿奇索通用交易发货失败 jd_order_no={order.jd_order_no} error={e}")
        return None


def refund_game(shop, order):
    """游戏点卡退款"""
    timestamp = str(int(datetime.now().timestamp()))
    params = {
        "appId": shop.agiso_app_id,
        "timestamp": timestamp,
        "tid": order.order_id
    }
    params["sign"] = agiso_sign(params, shop.agiso_app_secret)

    url = f"{get_agiso_base_url(shop)}/aldsJd/GameCard/Refund"
    try:
        resp = requests.post(url, json=params, headers=get_agiso_headers(shop), timeout=15)
        result = resp.json()
        logger.info(f"阿奇索游戏点卡退款 order_id={order.order_id} result={result}")
        return result
    except Exception as e:
        logger.error(f"阿奇索游戏点卡退款失败 order_id={order.order_id} error={e}")
        return None


def refund_general(shop, order):
    """通用交易退款"""
    timestamp = str(int(datetime.now().timestamp()))
    params = {
        "appId": shop.agiso_app_id,
        "timestamp": timestamp,
        "tid": order.jd_order_no
    }
    params["sign"] = agiso_sign(params, shop.agiso_app_secret)

    url = f"{get_agiso_base_url(shop)}/aldsJd/Vtp/Refund"
    try:
        resp = requests.post(url, json=params, headers=get_agiso_headers(shop), timeout=15)
        result = resp.json()
        logger.info(f"阿奇索通用交易退款 jd_order_no={order.jd_order_no} result={result}")
        return result
    except Exception as e:
        logger.error(f"阿奇索通用交易退款失败 jd_order_no={order.jd_order_no} error={e}")
        return None


def verify_agiso_push_sign(params: dict, json_body: str, timestamp: str, app_secret: str) -> bool:
    """
    验证阿奇索推送签名
    MD5(AppSecret + json{json内容} + timestamp{时间戳} + AppSecret)
    """
    import hashlib
    plain = f"{app_secret}json{json_body}timestamp{timestamp}{app_secret}"
    expected = hashlib.md5(plain.encode('utf-8')).hexdigest()
    return params.get('sign', '') == expected
