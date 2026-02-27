import json
import logging
import requests
from datetime import datetime
from app.utils.sign import game_sign, general_sign
from app.utils.crypto import base64_encode, aes_encrypt

logger = logging.getLogger(__name__)


def callback_game_success(shop, order, card_infos=None):
    """
    回调京东游戏点卡成功
    - 直充：data = base64({"orderId": "xxx", "orderStatus": "0"})
    - 卡密：data = base64({"orderId": "xxx", "orderStatus": "0", "cardInfos": [{"cardNo": "xxx", "cardPass": "xxx"}]})
    """
    payload = {
        "orderId": order.order_id,
        "orderStatus": "0"
    }
    if card_infos:
        payload["cardInfos"] = card_infos

    data_str = json.dumps(payload, ensure_ascii=False)
    data_b64 = base64_encode(data_str)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    params = {
        "customerId": shop.game_customer_id,
        "timestamp": timestamp,
        "data": data_b64
    }
    sign = game_sign(params, shop.game_md5_secret)
    params["sign"] = sign

    # 确定回调URL
    if card_infos and shop.game_card_callback_url:
        callback_url = shop.game_card_callback_url
    elif not card_infos and shop.game_direct_callback_url:
        callback_url = shop.game_direct_callback_url
    else:
        callback_url = shop.game_api_url

    return _do_callback(callback_url, params, order, is_json=True)


def callback_game_refund(shop, order):
    """
    回调京东游戏点卡退款
    data = base64({"orderId": "xxx", "orderStatus": "2", "failedCode": 999, "failedReason": "商家退款"})
    """
    payload = {
        "orderId": order.order_id,
        "orderStatus": "2",
        "failedCode": 999,
        "failedReason": "商家退款"
    }
    data_str = json.dumps(payload, ensure_ascii=False)
    data_b64 = base64_encode(data_str)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    params = {
        "customerId": shop.game_customer_id,
        "timestamp": timestamp,
        "data": data_b64
    }
    sign = game_sign(params, shop.game_md5_secret)
    params["sign"] = sign

    callback_url = shop.game_api_url
    return _do_callback(callback_url, params, order, is_json=True)


def callback_general_success(shop, order, product=None):
    """
    回调京东通用交易成功
    POST to notifyUrl + /produce/result
    produceStatus=1，如有卡密则附带 product（AES加密）
    """
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    params = {
        "vendorId": shop.general_vendor_id or order.vendor_id,
        "jdOrderNo": order.jd_order_no,
        "agentOrderNo": order.agent_order_no,
        "produceStatus": "1",
        "quantity": str(order.quantity or 1),
        "timestamp": timestamp,
        "signType": "MD5"
    }
    if product:
        # AES加密卡密数据
        encrypted_product = aes_encrypt(product, shop.general_aes_secret)
        params["product"] = encrypted_product

    sign = general_sign(params, shop.general_md5_secret)
    params["sign"] = sign

    callback_url = (order.notify_url or shop.general_callback_url or '') + '/produce/result'
    return _do_callback(callback_url, params, order, is_json=False)


def callback_general_refund(shop, order):
    """
    回调京东通用交易退款
    produceStatus=2
    """
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    params = {
        "vendorId": shop.general_vendor_id or order.vendor_id,
        "jdOrderNo": order.jd_order_no,
        "agentOrderNo": order.agent_order_no,
        "produceStatus": "2",
        "quantity": str(order.quantity or 1),
        "timestamp": timestamp,
        "signType": "MD5"
    }
    sign = general_sign(params, shop.general_md5_secret)
    params["sign"] = sign

    callback_url = (order.notify_url or shop.general_callback_url or '') + '/produce/result'
    return _do_callback(callback_url, params, order, is_json=False)


def _do_callback(url, params, order, is_json=True):
    """执行实际的HTTP回调请求"""
    from app.extensions import db
    try:
        if is_json:
            resp = requests.post(url, json=params, timeout=10)
        else:
            resp = requests.post(url, data=params, timeout=10)

        result = resp.json()
        # 游戏点卡：retCode=="100"；通用交易：code=="0"
        success = result.get('retCode') == '100' or result.get('code') == '0'

        order.notify_status = 1 if success else 2
        db.session.commit()
        logger.info(f"回调成功 order_id={order.order_id} url={url} response={result}")
        return success, result
    except Exception as e:
        order.notify_status = 2
        db.session.commit()
        logger.error(f"回调失败 order_id={order.order_id} url={url} error={e}")
        return False, str(e)
