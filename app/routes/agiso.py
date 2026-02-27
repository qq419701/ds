import json
import logging
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.shop import Shop
from app.models.order import Order

agiso_bp = Blueprint('agiso', __name__)
logger = logging.getLogger(__name__)


@agiso_bp.route('/api/agiso/push', methods=['POST'])
def agiso_push():
    """接收阿奇索推送通知"""
    # 1. 获取URL参数
    timestamp = request.args.get('timestamp', '')
    sign = request.args.get('sign', '')
    aopic = request.args.get('aopic', '')
    from_platform = request.args.get('fromPlatform', '')

    # 2. 获取表单参数
    json_body = request.form.get('json', '')

    logger.info(f"阿奇索推送 aopic={aopic} timestamp={timestamp}")

    # 3. 解析JSON数据
    try:
        push_data = json.loads(json_body) if json_body else {}
    except Exception as e:
        logger.error(f"推送数据解析失败: {e}")
        return jsonify({"code": "1", "message": "数据格式错误"})

    # 4. 查找对应店铺并验证签名（使用appId匹配）
    app_id = push_data.get('appId', '')
    shop = Shop.query.filter_by(agiso_app_id=str(app_id)).first()

    if shop and shop.agiso_app_secret:
        from app.services.agiso_service import verify_agiso_push_sign
        if not verify_agiso_push_sign(
            {'sign': sign},
            json_body,
            timestamp,
            shop.agiso_app_secret
        ):
            logger.warning(f"阿奇索推送签名验证失败 appId={app_id}")
            # 不阻断，继续处理（可根据需要开启严格验证）

    # 5. 根据aopic类型处理
    aopic_int = int(aopic) if aopic.isdigit() else 0

    if aopic_int == 8:
        # 游戏点卡订单支付成功 → 记录订单信息
        _handle_game_paid(shop, push_data)
    elif aopic_int == 2:
        # 付款后自动发货完成 → 更新订单状态并回调京东
        _handle_auto_deliver_complete(shop, push_data)
    elif aopic_int == 16:
        # 通用交易订单支付成功 → 记录订单信息
        _handle_general_paid(shop, push_data)
    else:
        logger.info(f"未处理的推送类型 aopic={aopic}")

    return jsonify({"code": "0", "message": "成功"})


def _handle_game_paid(shop, push_data):
    """处理游戏点卡订单支付成功推送"""
    tid = str(push_data.get('tid', ''))
    order = Order.query.filter_by(order_id=tid).first()
    if order and order.order_status == 0:
        order.order_status = 1
        db.session.commit()
        logger.info(f"游戏点卡订单支付 order_id={tid}")


def _handle_auto_deliver_complete(shop, push_data):
    """处理自动发货完成推送"""
    tid = str(push_data.get('tid', ''))
    order = Order.query.filter_by(order_id=tid).first()
    if not order:
        logger.warning(f"订单不存在 tid={tid}")
        return

    # 提取卡密数据
    card_list = push_data.get('cardList', [])
    if not shop:
        shop_obj = order.shop
    else:
        shop_obj = shop

    if order.shop_type == 1:
        # 游戏点卡回调
        if order.order_type == 1:
            # 直充
            order.order_status = 2
            db.session.commit()
            from app.services.callback_service import callback_game_success
            callback_game_success(shop_obj, order)
        elif order.order_type == 2 and card_list:
            # 卡密
            card_infos = [{"cardNo": c.get('cardno', ''), "cardPass": c.get('cardpass', '')}
                         for c in card_list]
            order.order_status = 2
            order.card_info = json.dumps(card_infos, ensure_ascii=False)
            db.session.commit()
            from app.services.callback_service import callback_game_success
            callback_game_success(shop_obj, order, card_infos=card_infos)
    elif order.shop_type == 2:
        # 通用交易回调
        order.order_status = 2
        db.session.commit()
        from app.services.callback_service import callback_general_success
        callback_general_success(shop_obj, order)


def _handle_general_paid(shop, push_data):
    """处理通用交易订单支付成功推送"""
    tid = str(push_data.get('tid', ''))
    order = Order.query.filter_by(jd_order_no=tid).first()
    if order and order.order_status in (0, 1):
        order.order_status = 1
        db.session.commit()
        logger.info(f"通用交易订单支付 jd_order_no={tid}")
