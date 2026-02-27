import json
import logging
from flask import Blueprint, request, jsonify, current_app
from app.extensions import db
from app.models.shop import Shop
from app.models.order import Order
from app.utils.sign import verify_game_sign
from app.utils.crypto import base64_decode, base64_encode
from app.utils.ip_whitelist import check_ip

game_bp = Blueprint('game', __name__)
logger = logging.getLogger(__name__)


def get_shop_by_customer_id(customer_id):
    """根据customerId找到对应的店铺"""
    return Shop.query.filter_by(game_customer_id=str(customer_id)).first()


@game_bp.route('/api/game/direct', methods=['POST'])
def game_direct():
    """游戏点卡直充接单"""
    # 1. 获取请求参数
    if request.is_json:
        req_data = request.get_json() or {}
    else:
        req_data = request.form.to_dict()

    customer_id = str(req_data.get('customerId', ''))
    data_b64 = req_data.get('data', '')
    timestamp = req_data.get('timestamp', '')
    sign = req_data.get('sign', '')

    # 2. 验证IP白名单
    if not check_ip(request):
        logger.warning(f"IP拦截 remote_addr={request.remote_addr}")
        return jsonify({"retCode": "111", "retMessage": "IP不在白名单"}), 403

    # 3. 找到对应店铺
    shop = get_shop_by_customer_id(customer_id)
    if not shop:
        logger.warning(f"店铺不存在 customerId={customer_id}")
        return jsonify({"retCode": "111", "retMessage": "商家编号不存在"})

    # 4. 验证签名
    if not current_app.config.get('SKIP_SIGN_VERIFY', False):
        params_to_sign = {
            "customerId": customer_id,
            "data": data_b64,
            "timestamp": timestamp
        }
        if not verify_game_sign({**params_to_sign, "sign": sign}, shop.game_md5_secret):
            logger.warning(f"签名验证失败 customerId={customer_id}")
            return jsonify({"retCode": "111", "retMessage": "签名错误"})

    # 5. Base64解码 data 字段
    try:
        order_data = json.loads(base64_decode(data_b64))
    except Exception as e:
        logger.error(f"data解析失败: {e}")
        return jsonify({"retCode": "111", "retMessage": "数据格式错误"})

    # 6. 处理订单
    from app.services.game_service import process_game_direct_order, auto_deliver_direct
    order, is_new = process_game_direct_order(shop, order_data, customer_id)

    if not is_new:
        logger.info(f"重复订单 order_id={order.order_id}")
        return jsonify({"retCode": "111", "retMessage": "订单号不允许重复"})

    # 7. 根据模式处理
    if shop.agiso_enabled == 1:
        # 阿奇索自动发货
        from app.services.agiso_service import send_game_direct
        send_game_direct(shop, order)
    elif shop.auto_deliver == 1:
        # 假发货模式
        auto_deliver_direct(shop, order)

    return jsonify({"retCode": "100", "retMessage": "成功"})


@game_bp.route('/api/game/query', methods=['POST'])
def game_query():
    """游戏点卡直充查询"""
    if request.is_json:
        req_data = request.get_json() or {}
    else:
        req_data = request.form.to_dict()

    customer_id = str(req_data.get('customerId', ''))
    data_b64 = req_data.get('data', '')
    timestamp = req_data.get('timestamp', '')
    sign = req_data.get('sign', '')

    if not check_ip(request):
        return jsonify({"retCode": "111", "retMessage": "IP不在白名单"}), 403

    shop = get_shop_by_customer_id(customer_id)
    if not shop:
        return jsonify({"retCode": "111", "retMessage": "商家编号不存在"})

    if not current_app.config.get('SKIP_SIGN_VERIFY', False):
        params_to_sign = {"customerId": customer_id, "data": data_b64, "timestamp": timestamp}
        if not verify_game_sign({**params_to_sign, "sign": sign}, shop.game_md5_secret):
            return jsonify({"retCode": "111", "retMessage": "签名错误"})

    try:
        query_data = json.loads(base64_decode(data_b64))
    except Exception as e:
        return jsonify({"retCode": "111", "retMessage": "数据格式错误"})

    order_id = str(query_data.get('orderId', ''))
    order = Order.query.filter_by(order_id=order_id).first()
    if not order:
        return jsonify({"retCode": "111", "retMessage": "订单不存在"})

    # orderStatus: 0=成功，1=处理中
    if order.order_status == 2:
        order_status = 0
    else:
        order_status = 1

    result_data = json.dumps({"orderStatus": order_status}, ensure_ascii=False)
    return jsonify({
        "retCode": "100",
        "retMessage": "查询成功",
        "data": base64_encode(result_data)
    })


@game_bp.route('/api/game/card', methods=['POST'])
def game_card():
    """游戏点卡卡密接单"""
    if request.is_json:
        req_data = request.get_json() or {}
    else:
        req_data = request.form.to_dict()

    customer_id = str(req_data.get('customerId', ''))
    data_b64 = req_data.get('data', '')
    timestamp = req_data.get('timestamp', '')
    sign = req_data.get('sign', '')

    if not check_ip(request):
        return jsonify({"retCode": "111", "retMessage": "IP不在白名单"}), 403

    shop = get_shop_by_customer_id(customer_id)
    if not shop:
        return jsonify({"retCode": "111", "retMessage": "商家编号不存在"})

    if not current_app.config.get('SKIP_SIGN_VERIFY', False):
        params_to_sign = {"customerId": customer_id, "data": data_b64, "timestamp": timestamp}
        if not verify_game_sign({**params_to_sign, "sign": sign}, shop.game_md5_secret):
            return jsonify({"retCode": "111", "retMessage": "签名错误"})

    try:
        order_data = json.loads(base64_decode(data_b64))
    except Exception as e:
        return jsonify({"retCode": "111", "retMessage": "数据格式错误"})

    from app.services.game_service import process_game_card_order, auto_deliver_card
    order, is_new = process_game_card_order(shop, order_data, customer_id)

    if not is_new:
        # 重复请求，若已有卡密则返回
        if order.card_info and order.order_status == 2:
            card_infos = json.loads(order.card_info)
            result_data = json.dumps({"cardinfos": card_infos}, ensure_ascii=False)
            return jsonify({
                "retCode": "100",
                "retMessage": "成功",
                "data": base64_encode(result_data)
            })
        return jsonify({"retCode": "100", "retMessage": "成功", "data": ""})

    if shop.agiso_enabled == 1:
        from app.services.agiso_service import send_game_card
        send_game_card(shop, order, '')
    elif shop.auto_deliver == 1:
        auto_deliver_card(shop, order)
        if order.card_info and order.order_status == 2:
            card_infos = json.loads(order.card_info)
            result_data = json.dumps({"cardinfos": card_infos}, ensure_ascii=False)
            return jsonify({
                "retCode": "100",
                "retMessage": "成功",
                "data": base64_encode(result_data)
            })

    return jsonify({"retCode": "100", "retMessage": "成功", "data": ""})


@game_bp.route('/api/game/card-query', methods=['POST'])
def game_card_query():
    """游戏点卡卡密查询"""
    if request.is_json:
        req_data = request.get_json() or {}
    else:
        req_data = request.form.to_dict()

    customer_id = str(req_data.get('customerId', ''))
    data_b64 = req_data.get('data', '')
    timestamp = req_data.get('timestamp', '')
    sign = req_data.get('sign', '')

    if not check_ip(request):
        return jsonify({"retCode": "111", "retMessage": "IP不在白名单"}), 403

    shop = get_shop_by_customer_id(customer_id)
    if not shop:
        return jsonify({"retCode": "111", "retMessage": "商家编号不存在"})

    if not current_app.config.get('SKIP_SIGN_VERIFY', False):
        params_to_sign = {"customerId": customer_id, "data": data_b64, "timestamp": timestamp}
        if not verify_game_sign({**params_to_sign, "sign": sign}, shop.game_md5_secret):
            return jsonify({"retCode": "111", "retMessage": "签名错误"})

    try:
        query_data = json.loads(base64_decode(data_b64))
    except Exception as e:
        return jsonify({"retCode": "111", "retMessage": "数据格式错误"})

    order_id = str(query_data.get('orderId', ''))
    order = Order.query.filter_by(order_id=order_id).first()
    if not order:
        return jsonify({"retCode": "111", "retMessage": "订单不存在"})

    if order.order_status == 2 and order.card_info:
        card_infos = json.loads(order.card_info)
        result_data = json.dumps({
            "orderStatus": "0",
            "cardinfos": card_infos
        }, ensure_ascii=False)
        return jsonify({
            "retCode": "100",
            "retMessage": "充值成功",
            "data": base64_encode(result_data)
        })
    elif order.order_status == 4:
        result_data = json.dumps({"orderStatus": "2"}, ensure_ascii=False)
        return jsonify({
            "retCode": "100",
            "retMessage": "查询成功",
            "data": base64_encode(result_data)
        })
    else:
        result_data = json.dumps({"orderStatus": "1"}, ensure_ascii=False)
        return jsonify({
            "retCode": "100",
            "retMessage": "查询成功",
            "data": base64_encode(result_data)
        })
