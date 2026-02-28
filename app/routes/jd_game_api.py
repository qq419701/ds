"""京东游戏点卡平台API接口。

提供给京东游戏点卡平台调用的接口：
- 直充接单、直充订单查询
- 卡密接单、卡密订单查询

京东推单格式: customerId=xxx&data=base64(JSON)&sign=xxx&timestamp=xxx
data字段使用UTF-8字符集进行Base64编码，内含业务JSON数据。
"""
import base64
import json
import logging
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models.order import Order
from app.models.shop import Shop
from app.services.jd_game import (
    verify_game_sign,
    callback_game_direct_success,
    callback_game_card_deliver,
)
from app.services.notification import send_order_notification

logger = logging.getLogger(__name__)

jd_game_api_bp = Blueprint('jd_game_api', __name__)


def decode_data(data_b64):
    """解码京东推送的Base64编码data字段。

    优先尝试UTF-8解码（接口文档规定），失败时回退GBK（兼容旧版）。

    Args:
        data_b64: Base64编码的字符串

    Returns:
        dict: 解码后的业务数据字典，解码失败时返回空字典
    """
    try:
        decoded_bytes = base64.b64decode(data_b64)
        # 优先UTF-8（接口文档规定字符编码UTF-8），回退GBK（兼容老平台）
        try:
            decoded_str = decoded_bytes.decode('utf-8')
        except Exception:
            decoded_str = decoded_bytes.decode('gbk', errors='replace')
        return json.loads(decoded_str)
    except Exception as e:
        logger.warning(f"解码data字段失败: {e}, data_b64={data_b64!r}")
        return {}


def encode_data(data_obj):
    """将字典编码为京东格式的Base64字符串（UTF-8字符集）。

    Args:
        data_obj: 要编码的字典

    Returns:
        str: Base64编码的字符串
    """
    json_str = json.dumps(data_obj, ensure_ascii=False)
    return base64.b64encode(json_str.encode('utf-8')).decode('ascii')


def _success_response(message='成功'):
    """返回京东格式的成功响应"""
    return jsonify(retCode='100', retMessage=message)


def _error_response(message='失败'):
    """返回京东格式的错误响应"""
    return jsonify(retCode='200', retMessage=message)


def _find_shop_by_request(data):
    """根据请求数据查找店铺"""
    # 京东可能传 customerId / shop_code / venderId
    customer_id = data.get('customerId') or data.get('customer_id')
    shop_code = data.get('shop_code')
    vender_id = data.get('venderId') or data.get('vender_id')

    shop = None
    if customer_id:
        shop = Shop.query.filter_by(game_customer_id=str(customer_id), is_enabled=1).first()
    if not shop and shop_code:
        shop = Shop.query.filter_by(shop_code=shop_code, is_enabled=1).first()
    if not shop and vender_id:
        shop = Shop.query.filter_by(shop_code=str(vender_id), is_enabled=1).first()

    return shop


def _check_shop_expire(shop):
    """检查店铺是否过期"""
    if shop.expire_time and shop.expire_time < datetime.utcnow():
        return False
    return True


@jd_game_api_bp.route('/direct', methods=['POST'])
def game_direct_order():
    """游戏点卡 - 直充接单接口

    京东推送格式: customerId=xxx&data=base64(JSON)&sign=xxx&timestamp=xxx
    data解码后: {"buyNum":"1","orderId":"xxx","totalPrice":"1.00","gameAccount":"6",...}
    返回: {"retCode": "100", "retMessage": "接收成功"}
    """
    raw = request.form.to_dict() or request.get_json(silent=True) or {}
    logger.info(f"=== 京东直充推送原始数据: {raw}")

    if not raw:
        return _error_response('无效请求数据')

    # 解析base64编码的data字段，提取业务数据
    data_b64 = raw.get('data', '')
    if data_b64:
        biz = decode_data(data_b64)
        logger.info(f"=== 京东直充data解码: {biz}")
    else:
        biz = raw

    # 匹配店铺（用外层的customerId）
    shop = _find_shop_by_request(raw)
    if not shop:
        shop = Shop.query.filter_by(shop_type=1, is_enabled=1).first()

    if not shop:
        return _error_response('店铺不存在或已禁用')

    if shop.expire_time and shop.expire_time < datetime.utcnow():
        return _error_response('店铺已到期')

    # 签名验证（用外层参数: customerId, data, timestamp, sign）
    if shop.game_md5_secret:
        if not verify_game_sign(raw, shop.game_md5_secret):
            logger.warning("游戏直充签名验证失败: shop=%s", shop.shop_code)
            return _error_response('签名验证失败')

    # 从解码后的业务数据中取字段
    jd_order_no = str(biz.get('orderId') or biz.get('jdOrderId') or '')

    if not jd_order_no:
        return _error_response('缺少订单号')

    # 防重复
    if Order.query.filter_by(jd_order_no=jd_order_no).first():
        return _success_response('订单已存在')

    order_no = f"ORD{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"

    order = Order(
        order_no=order_no,
        jd_order_no=jd_order_no,
        shop_id=shop.id,
        shop_type=1,
        order_type=1,
        order_status=0,
        sku_id=str(biz.get('skuId') or ''),
        product_info=f"SKU:{biz.get('skuId', '')} Brand:{biz.get('brandId', '')}",
        amount=int(float(biz.get('totalPrice') or biz.get('price') or 0) * 100),
        quantity=int(biz.get('buyNum') or biz.get('num') or 1),
        produce_account=biz.get('gameAccount') or biz.get('chargeAccount') or biz.get('phoneNum') or '',
        notify_url='',
    )

    db.session.add(order)
    db.session.commit()
    logger.info(f"直充订单接收成功: jd={jd_order_no}, local={order_no}, amount={order.amount}, account={order.produce_account}")

    # 记录订单创建事件
    try:
        from app.models.order_event import OrderEvent
        create_event = OrderEvent(
            order_id=order.id,
            order_no=order.order_no,
            event_type='order_created',
            event_desc=f'游戏点卡直充订单创建，京东订单号：{jd_order_no}，金额：{order.amount/100:.2f}元，账号：{order.produce_account or "无"}',
            result='info',
        )
        db.session.add(create_event)
        db.session.commit()
    except Exception as e:
        logger.warning(f"记录订单创建事件失败: {e}")

    try:
        send_order_notification(order, shop)
    except Exception:
        pass

    return _success_response('接收成功')


@jd_game_api_bp.route('/query', methods=['POST', 'GET'])
def game_direct_query():
    """游戏点卡 - 直充订单查询

    京东请求格式: customerId=xxx&data=base64({"orderId":"xxx"})&timestamp=xxx&sign=xxx
    返回: {"retCode":"100","retMessage":"查询成功","data":base64({"orderStatus":0})}

    orderStatus: 0=充值中 1=充值成功 2=充值失败
    """
    if request.method == 'GET':
        params = request.args.to_dict()
    else:
        params = request.form.to_dict()
        if not params:
            try:
                params = request.get_json(force=True) or {}
            except Exception:
                params = {}

    if not params:
        return _error_response('无效请求数据')

    # 从base64编码的data字段提取订单号（JD格式）
    data_b64 = params.get('data', '')
    if data_b64:
        biz_data = decode_data(data_b64)
        jd_order_no = str(biz_data.get('orderId', ''))
    else:
        jd_order_no = str(params.get('orderId') or params.get('jdOrderId') or '')

    if not jd_order_no:
        return _error_response('缺少订单号')

    order = Order.query.filter_by(jd_order_no=jd_order_no).first()
    if not order:
        return _error_response('订单不存在')

    # 状态映射：内部状态 -> JD游戏点卡直充状态
    # 0=充值中（待处理/处理中），1=充值成功，2=充值失败
    jd_status_map = {0: 0, 1: 0, 2: 1, 3: 2, 4: 2, 5: 2}
    jd_status = jd_status_map.get(order.order_status, 0)

    data_obj = {'orderStatus': jd_status}
    data_response = encode_data(data_obj)

    logger.info(f"直充查询: jd_order={jd_order_no}, local_status={order.order_status}, jd_status={jd_status}")

    return jsonify(
        retCode='100',
        retMessage='查询成功',
        data=data_response
    )


@jd_game_api_bp.route('/card', methods=['POST'])
def game_card_order():
    """游戏点卡 - 卡密接单接口

    京东推送格式: customerId=xxx&data=base64(JSON)&sign=xxx&timestamp=xxx
    """
    raw = request.form.to_dict() or request.get_json(silent=True) or {}
    logger.info(f"=== 京东卡密推送原始数据: {raw}")

    if not raw:
        return _error_response('无效请求数据')

    data_b64 = raw.get('data', '')
    if data_b64:
        biz = decode_data(data_b64)
        logger.info(f"=== 京东卡密data解码: {biz}")
    else:
        biz = raw

    shop = _find_shop_by_request(raw)
    if not shop:
        shop = Shop.query.filter_by(shop_type=1, is_enabled=1).first()

    if not shop:
        return _error_response('店铺不存在或已禁用')

    if shop.expire_time and shop.expire_time < datetime.utcnow():
        return _error_response('店铺已到期')

    if shop.game_md5_secret:
        if not verify_game_sign(raw, shop.game_md5_secret):
            logger.warning("游戏卡密签名验证失败: shop=%s", shop.shop_code)
            return _error_response('签名验证失败')

    jd_order_no = str(biz.get('orderId') or biz.get('jdOrderId') or '')

    if not jd_order_no:
        return _error_response('缺少订单号')

    if Order.query.filter_by(jd_order_no=jd_order_no).first():
        return _success_response('订单已存在')

    order_no = f"ORD{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"

    order = Order(
        order_no=order_no,
        jd_order_no=jd_order_no,
        shop_id=shop.id,
        shop_type=1,
        order_type=2,
        order_status=0,
        sku_id=str(biz.get('skuId') or ''),
        product_info=f"SKU:{biz.get('skuId', '')} Brand:{biz.get('brandId', '')}",
        amount=int(float(biz.get('totalPrice') or biz.get('price') or 0) * 100),
        quantity=int(biz.get('buyNum') or biz.get('num') or 1),
        produce_account=biz.get('gameAccount') or biz.get('chargeAccount') or biz.get('phoneNum') or '',
        notify_url='',
    )

    db.session.add(order)
    db.session.commit()
    logger.info(f"卡密订单接收成功: jd={jd_order_no}, local={order_no}, amount={order.amount}")

    # 记录订单创建事件
    try:
        from app.models.order_event import OrderEvent
        create_event = OrderEvent(
            order_id=order.id,
            order_no=order.order_no,
            event_type='order_created',
            event_desc=f'游戏点卡卡密订单创建，京东订单号：{jd_order_no}，SKU：{order.sku_id or "无"}，数量：{order.quantity}',
            result='info',
        )
        db.session.add(create_event)
        db.session.commit()
    except Exception as e:
        logger.warning(f"记录订单创建事件失败: {e}")

    # 91卡券自动发货（根据商品配置，deliver_type=1时自动提卡）
    try:
        from app.models.product import Product
        from app.models.order_event import OrderEvent
        product = None
        if order.sku_id:
            product = Product.query.filter_by(
                shop_id=shop.id, sku_id=order.sku_id, is_enabled=1, deliver_type=1
            ).first()
        if product and shop.card91_api_key:
            from app.services.card91 import card91_auto_deliver
            ok, msg, cards = card91_auto_deliver(shop, order, product)
            fetch_event = OrderEvent(
                order_id=order.id,
                order_no=order.order_no,
                event_type='card91_fetch',
                event_desc=f'91卡券自动提卡：{msg}',
                result='success' if ok else 'failed',
            )
            db.session.add(fetch_event)
            if ok:
                order.set_card_info(cards)
                success, callback_msg = callback_game_card_deliver(shop, order, cards)
                if success:
                    order.order_status = 2
                    order.deliver_time = datetime.utcnow()
                    order.notify_status = 1
                    order.notify_time = datetime.utcnow()
                    deliver_event = OrderEvent(
                        order_id=order.id,
                        order_no=order.order_no,
                        event_type='card91_deliver',
                        event_desc=f'91卡券自动发卡成功，共{len(cards)}张',
                        result='success',
                    )
                    db.session.add(deliver_event)
                    logger.info(f"卡密订单 {order_no} 91卡券自动发货完成")
                else:
                    order.notify_status = 2
                    error_event = OrderEvent(
                        order_id=order.id,
                        order_no=order.order_no,
                        event_type='error',
                        event_desc=f'91卡券发卡回调失败：{callback_msg}',
                        result='failed',
                    )
                    db.session.add(error_event)
            db.session.commit()
    except Exception as e:
        logger.error(f"91卡券自动发货失败: {e}")

    try:
        send_order_notification(order, shop)
    except Exception:
        pass

    return _success_response('接收成功')


@jd_game_api_bp.route('/card-query', methods=['POST', 'GET'])
def game_card_query():
    """游戏点卡 - 卡密订单查询

    京东请求格式: customerId=xxx&data=base64({"orderId":"xxx"})&timestamp=xxx&sign=xxx
    返回: {"retCode":"100","retMessage":"查询成功","data":base64({"orderStatus":0})}
    """
    if request.method == 'GET':
        params = request.args.to_dict()
    else:
        params = request.form.to_dict()
        if not params:
            try:
                params = request.get_json(force=True) or {}
            except Exception:
                params = {}

    if not params:
        return _error_response('无效请求数据')

    data_b64 = params.get('data', '')
    if data_b64:
        biz_data = decode_data(data_b64)
        jd_order_no = str(biz_data.get('orderId', ''))
    else:
        jd_order_no = str(params.get('orderId') or params.get('jdOrderId') or '')

    if not jd_order_no:
        return _error_response('缺少订单号')

    order = Order.query.filter_by(jd_order_no=jd_order_no).first()
    if not order:
        return _error_response('订单不存在')

    jd_status_map = {
        0: 1, 1: 1, 2: 0, 3: 2, 4: 2, 5: 2,
    }
    jd_status = jd_status_map.get(order.order_status, 1)

    data_obj = {'orderStatus': jd_status}

    if order.order_status == 2 and order.card_info_parsed:
        raw_cards = order.card_info_parsed
        jd_cards = []
        for card in raw_cards:
            card_no = card.get('cardNo') or card.get('card_no') or ''
            card_pass = card.get('cardPass') or card.get('cardPwd') or card.get('card_pwd') or ''
            jd_cards.append({'cardNo': card_no, 'cardPass': card_pass})
        data_obj['cardInfos'] = jd_cards

    data_response = encode_data(data_obj)

    logger.info(f"卡密查询: jd_order={jd_order_no}, local_status={order.order_status}, jd_status={jd_status}")

    return jsonify(
        retCode='100',
        retMessage='查询成功',
        data=data_response
    )
