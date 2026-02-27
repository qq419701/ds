import hmac
import hashlib
import base64
import json
import time
import logging
from urllib.parse import quote_plus

import threading
import requests

from app.extensions import db
from app.models.notification_log import NotificationLog

logger = logging.getLogger(__name__)

RETRY_INTERVALS = [1, 3, 5]


def build_order_message(order, shop):
    """Build notification message for an order."""
    return (
        f"### 📦 新订单通知\n\n"
        f"**订单号：** {order.jd_order_no}\n\n"
        f"**店铺：** {shop.shop_name}\n\n"
        f"**商品：** {order.product_info or '-'}\n\n"
        f"**金额：** ¥{order.amount_yuan}\n\n"
        f"**数量：** {order.quantity}\n\n"
        f"**充值账号：** {order.produce_account or '-'}\n\n"
        f"**创建时间：** {order.create_time.strftime('%Y-%m-%d %H:%M:%S') if order.create_time else '-'}\n\n"
        f"> 请及时处理订单"
    )


def _generate_dingtalk_sign(timestamp, secret):
    """Generate DingTalk webhook signature."""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    return quote_plus(base64.b64encode(hmac_code).decode('utf-8'))


def send_dingtalk(webhook, secret, message):
    """Send DingTalk notification.

    Returns (success: bool, response_text: str, error: str|None)
    """
    try:
        url = webhook
        if secret:
            timestamp = str(round(time.time() * 1000))
            sign = _generate_dingtalk_sign(timestamp, secret)
            sep = '&' if '?' in webhook else '?'
            url = f"{webhook}{sep}timestamp={timestamp}&sign={sign}"

        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": "新订单通知",
                "text": message
            }
        }

        resp = requests.post(url, json=data, timeout=10)
        resp_text = resp.text
        result = resp.json()
        if result.get('errcode', -1) == 0:
            return True, resp_text, None
        return False, resp_text, result.get('errmsg', '未知错误')
    except Exception as e:
        logger.exception("DingTalk notification failed")
        return False, '', str(e)


def send_wecom(webhook, message):
    """Send WeCom (Enterprise WeChat) notification.

    Returns (success: bool, response_text: str, error: str|None)
    """
    try:
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": message
            }
        }

        resp = requests.post(webhook, json=data, timeout=10)
        resp_text = resp.text
        result = resp.json()
        if result.get('errcode', -1) == 0:
            return True, resp_text, None
        return False, resp_text, result.get('errmsg', '未知错误')
    except Exception as e:
        logger.exception("WeCom notification failed")
        return False, '', str(e)


def _do_send(notify_type, shop, message):
    """Execute send for a specific notification type."""
    if notify_type == 'dingtalk' and shop.dingtalk_webhook:
        return send_dingtalk(shop.dingtalk_webhook, shop.dingtalk_secret, message)
    elif notify_type == 'wecom' and shop.wecom_webhook:
        return send_wecom(shop.wecom_webhook, message)
    return False, '', '未配置通知渠道'


def _send_notification_sync(app, order_id, shop_id, message, channels):
    """在后台线程中同步发送通知（带重试）"""
    with app.app_context():
        from app.models.order import Order as _Order
        from app.models.shop import Shop as _Shop
        from datetime import datetime

        order = db.session.get(_Order, order_id)
        shop = db.session.get(_Shop, shop_id)
        if not order or not shop:
            return

        for channel in channels:
            success = False
            resp_text = ''
            error_msg = None

            for attempt, wait in enumerate(RETRY_INTERVALS):
                ok, resp_text, err = _do_send(channel, shop, message)
                if ok:
                    success = True
                    error_msg = None
                    break
                error_msg = err
                if attempt < len(RETRY_INTERVALS) - 1:
                    time.sleep(wait)

            log = NotificationLog(
                order_id=order.id,
                shop_id=shop.id,
                notify_type=channel,
                notify_status=1 if success else 0,
                request_data=json.dumps({"message": message[:500]}, ensure_ascii=False),
                response_data=resp_text[:2000] if resp_text else None,
                error_message=error_msg,
            )
            db.session.add(log)

        order.notified = 1
        order.notify_send_time = datetime.utcnow()
        db.session.commit()


def send_order_notification(order, shop):
    """Send order notification via configured channels (async)."""
    if shop.notify_enabled != 1:
        return

    message = build_order_message(order, shop)

    channels = []
    if shop.dingtalk_webhook:
        channels.append('dingtalk')
    if shop.wecom_webhook:
        channels.append('wecom')

    if not channels:
        return

    from flask import current_app
    app = current_app._get_current_object()
    t = threading.Thread(
        target=_send_notification_sync,
        args=(app, order.id, shop.id, message, channels),
        daemon=True
    )
    t.start()


def resend_notification(log_id):
    """Resend a notification from a log entry."""
    from app.models.order import Order
    from app.models.shop import Shop

    log_entry = db.session.get(NotificationLog, log_id)
    if not log_entry:
        return False, '通知记录不存在'

    order = db.session.get(Order, log_entry.order_id)
    shop = db.session.get(Shop, log_entry.shop_id)
    if not order or not shop:
        return False, '订单或店铺不存在'

    message = build_order_message(order, shop)
    ok, resp_text, err = _do_send(log_entry.notify_type, shop, message)

    new_log = NotificationLog(
        order_id=order.id,
        shop_id=shop.id,
        notify_type=log_entry.notify_type,
        notify_status=1 if ok else 0,
        request_data=json.dumps({"message": message[:500]}, ensure_ascii=False),
        response_data=resp_text[:2000] if resp_text else None,
        error_message=err,
    )
    db.session.add(new_log)
    db.session.commit()

    return ok, err if not ok else '发送成功'


def send_test_notification(shop, notify_type):
    """Send a test notification for a shop."""
    message = (
        "### 🔔 测试通知\n\n"
        f"**店铺：** {shop.shop_name}\n\n"
        f"**类型：** {'钉钉' if notify_type == 'dingtalk' else '企业微信'}\n\n"
        f"**时间：** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "> 这是一条测试通知，收到此消息说明配置正确"
    )

    ok, resp_text, err = _do_send(notify_type, shop, message)
    return ok, err if not ok else '测试通知发送成功'
