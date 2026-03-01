"""阿奇索推送通知接收接口。

阿奇索在以下事件发生时向开发者配置的URL推送消息：
- 付款成功（aopic=1）
- 自动发货完成（aopic=2）
- 通用交易订单支付（aopic=16）
- 游戏点卡订单支付（aopic=8）

推送方式：POST，参数为：
- timestamp（Query参数）：时间戳
- sign（Query参数）：签名
- aopic（Query参数）：推送类型
- json（Form参数）：消息JSON

签名验证：MD5(AppSecret + json{value} + timestamp{value} + AppSecret)

配置推送URL：在阿奇索开发者后台设置推送地址，格式如：
https://your-domain.com/api/agiso/push
"""
import json
import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models.order import Order
from app.models.shop import Shop
from app.services.agiso import verify_agiso_push_sign

logger = logging.getLogger(__name__)

agiso_push_bp = Blueprint('agiso_push', __name__)


def _find_shop_by_app_id(app_id):
    """根据AppId查找店铺。"""
    return Shop.query.filter_by(agiso_app_id=str(app_id), is_enabled=1).first()


def _find_order_by_jd_no(jd_order_no):
    """根据京东订单号查找订单。"""
    return Order.query.filter_by(jd_order_no=str(jd_order_no)).first()


def _verify_push(shop, json_str, timestamp_str, sign):
    """验证推送签名（可选）。"""
    if not shop or not shop.agiso_app_secret:
        return True
    expected = verify_agiso_push_sign(json_str, timestamp_str, shop.agiso_app_secret)
    return expected == sign.lower()


@agiso_push_bp.route('/push', methods=['POST'])
def agiso_push():
    """接收阿奇索推送通知。

    处理付款成功和自动发货完成通知，更新订单状态。
    """
    timestamp_str = request.args.get('timestamp', '')
    sign = request.args.get('sign', '')
    aopic = request.args.get('aopic', '')
    json_str = request.form.get('json', '')

    logger.info(f"阿奇索推送: aopic={aopic}, timestamp={timestamp_str}, body={json_str[:500]}")

    if not json_str:
        return jsonify(success=False, message='缺少json参数'), 400

    try:
        msg = json.loads(json_str)
    except json.JSONDecodeError:
        logger.warning(f"阿奇索推送JSON解析失败: {json_str[:200]}")
        return jsonify(success=False, message='json格式错误'), 400

    # 处理游戏点卡订单（aopic=8）和自动发货完成（aopic=2）
    if aopic in ('8', '2', '1'):
        _handle_game_card_push(msg, aopic, json_str, timestamp_str, sign)

    # 处理通用交易订单（aopic=16）
    elif aopic == '16':
        _handle_general_push(msg, json_str, timestamp_str, sign)

    else:
        logger.info(f"阿奇索推送：忽略未知类型 aopic={aopic}")

    return jsonify(success=True, message='OK')


def _handle_game_card_push(msg, aopic, json_str, timestamp_str, sign):
    """处理游戏点卡推送（付款成功 / 自动发货完成）。"""
    jd_order_no = str(msg.get('OrderId') or msg.get('Tid') or '')
    if not jd_order_no:
        logger.warning(f"游戏点卡推送缺少订单号: {msg}")
        return

    order = _find_order_by_jd_no(jd_order_no)
    if not order:
        logger.info(f"阿奇索推送：订单 {jd_order_no} 不在本系统")
        return

    shop = order.shop
    if shop and not _verify_push(shop, json_str, timestamp_str, sign):
        logger.warning(f"阿奇索推送签名验证失败：shop={shop.shop_code}")
        return

    if aopic == '2':
        # 自动发货完成，提取卡密
        orders_data = msg.get('Orders', [])
        cards = []
        for sub in orders_data:
            for card_item in sub.get('SendCards', []):
                card_no = card_item.get('Card', '')
                card_pass = card_item.get('Pwd', '')
                cards.append({'cardNo': card_no, 'cardPass': card_pass})

        if cards and order.order_type == 2:
            order.set_card_info(cards)
            logger.info(f"阿奇索推送：订单 {jd_order_no} 收到 {len(cards)} 张卡密")

        order.order_status = 2
        order.deliver_time = datetime.now(timezone.utc)
        db.session.commit()
        logger.info(f"阿奇索推送：订单 {jd_order_no} 自动发货完成，状态已更新")

    elif aopic in ('1', '8'):
        # 付款成功，更新为处理中
        if order.order_status == 0:
            order.order_status = 1
            order.pay_time = datetime.now(timezone.utc)
            db.session.commit()
            logger.info(f"阿奇索推送：订单 {jd_order_no} 付款成功，状态更新为处理中")


def _handle_general_push(msg, json_str, timestamp_str, sign):
    """处理通用交易推送（aopic=16）。"""
    jd_order_no = str(msg.get('JdOrderNo') or '')
    if not jd_order_no:
        logger.warning(f"通用交易推送缺少JdOrderNo: {msg}")
        return

    order = _find_order_by_jd_no(jd_order_no)
    if not order:
        logger.info(f"阿奇索推送：通用交易订单 {jd_order_no} 不在本系统")
        return

    shop = order.shop
    if shop and not _verify_push(shop, json_str, timestamp_str, sign):
        logger.warning(f"阿奇索推送签名验证失败：shop={shop.shop_code}")
        return

    produce_status = msg.get('ProduceStatus', 3)
    if produce_status == 1:
        order.order_status = 2
        order.deliver_time = datetime.now(timezone.utc)
        db.session.commit()
        logger.info(f"阿奇索推送：通用交易订单 {jd_order_no} 生产成功")
    elif produce_status == 3:
        if order.order_status == 0:
            order.order_status = 1
            db.session.commit()
            logger.info(f"阿奇索推送：通用交易订单 {jd_order_no} 生产中")
