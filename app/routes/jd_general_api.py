"""京东通用交易平台API接口。

提供给京东通用交易平台调用的接口：
- 充值/提取卡密接口���distill）
- 反查订单接口（query）
"""
import json
import logging
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models.order import Order
from app.models.shop import Shop
from app.services.jd_general import verify_general_sign, generate_general_sign
from app.services.notification import send_order_notification

logger = logging.getLogger(__name__)

jd_general_api_bp = Blueprint('jd_general_api', __name__)


def _find_shop_by_request(data):
    """根据请求数据查找店铺"""
    # 通用交易文档中字段名为 vendorId（非 venderId）
    vendor_id = data.get('vendorId') or data.get('venderId') or data.get('vendor_id')
    shop_code = data.get('shop_code')

    shop = None
    if vendor_id:
        # 优先按 general_vendor_id 查找（通用交易商家ID）
        shop = Shop.query.filter_by(general_vendor_id=str(vendor_id), is_enabled=1).first()
        if not shop:
            shop = Shop.query.filter_by(shop_code=str(vendor_id), is_enabled=1).first()
    if not shop and shop_code:
        shop = Shop.query.filter_by(shop_code=shop_code, is_enabled=1).first()

    return shop


@jd_general_api_bp.route('/distill', methods=['POST'])
def general_distill():
    """通用交易 - 充值/提取卡密接口

    京东推送充值或卡密订单到此接口（application/x-www-form-urlencoded）
    """
    data = request.form.to_dict()
    if not data:
        data = request.get_json(silent=True) or {}
    if not data:
        return jsonify(success=False, code=1, message='无效请求数据'), 400

    shop = _find_shop_by_request(data)
    if not shop:
        return jsonify(success=False, code=1, message='店铺不存在或已禁用'), 400

    if shop.expire_time and shop.expire_time < datetime.utcnow():
        return jsonify(success=False, code=1, message='店铺已到期'), 403

    # 签名验证
    if shop.general_md5_secret:
        if not verify_general_sign(data, shop.general_md5_secret):
            logger.warning("通用交易签名验证失败: shop=%s", shop.shop_code)
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            resp_params = {
                'jdOrderNo': str(data.get('jdOrderNo') or ''),
                'agentOrderNo': '',
                'produceStatus': 2,
                'code': 'JDO_304',
                'signType': 'MD5',
                'timestamp': timestamp,
            }
            return jsonify(resp_params), 403

    jd_order_no = str(data.get('jdOrderNo') or data.get('jdOrderId') or
                      data.get('jd_order_no') or data.get('orderId') or '')

    # 防重复
    if jd_order_no and Order.query.filter_by(jd_order_no=jd_order_no).first():
        existing = Order.query.filter_by(jd_order_no=jd_order_no).first()
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        resp_params = {
            'jdOrderNo': jd_order_no,
            'agentOrderNo': existing.order_no,
            'produceStatus': 3,
            'code': 'JDO_201',
            'signType': 'MD5',
            'timestamp': timestamp,
        }
        if shop.general_md5_secret:
            sign_p = {k: v for k, v in resp_params.items()
                      if k not in ('sign', 'signType') and v is not None and str(v) != ''}
            resp_params['sign'] = generate_general_sign(sign_p, shop.general_md5_secret)
        return jsonify(resp_params)

    # 判断订单类型：通用交易 bizType=1直充 bizType=2卡密
    biz_type = data.get('bizType') or data.get('biz_type') or data.get('order_type')
    order_type = 2 if str(biz_type) == '2' else 1

    order_no = f"ORD{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"

    amount = int(data.get('totalPrice') or data.get('price') or data.get('amount') or
                 data.get('jdPrice') or 0)
    quantity = int(data.get('quantity') or data.get('num') or 1)
    produce_account = (data.get('produceAccount') or data.get('chargeAccount') or
                       data.get('produce_account') or data.get('account') or '')
    notify_url = data.get('notifyUrl') or data.get('notify_url') or ''
    sku_id = data.get('wareNo') or data.get('skuId') or data.get('sku_id') or ''

    order = Order(
        order_no=order_no,
        jd_order_no=jd_order_no,
        shop_id=shop.id,
        shop_type=2,  # 通用交易
        order_type=order_type,
        order_status=0,
        sku_id=sku_id,
        product_info=data.get('skuName') or data.get('product_info') or data.get('productInfo'),
        amount=amount,
        quantity=quantity,
        produce_account=produce_account,
        notify_url=notify_url,
    )

    db.session.add(order)
    db.session.commit()

    # 记录订单创建事件
    try:
        from app.models.order_event import OrderEvent
        create_event = OrderEvent(
            order_id=order.id,
            order_no=order.order_no,
            event_type='order_created',
            event_desc=f'通用交易订单创建，京东订单号：{jd_order_no}，类型：{"直充" if order_type==1 else "卡密"}，SKU：{sku_id or "无"}',
            result='info',
        )
        db.session.add(create_event)
        db.session.commit()
    except Exception as e:
        logger.warning(f"记录订单创建事件失败: {e}")

    # 91卡券自动发货（卡密订单，根据商品配置deliver_type=1时自动提卡）
    if order_type == 2:
        try:
            from app.models.product import Product
            from app.models.order_event import OrderEvent
            from app.services.jd_general import callback_general_card_deliver
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
                    success, callback_msg = callback_general_card_deliver(shop, order, cards)
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
                        logger.info(f"通用交易卡密订单 {order.order_no} 91卡券自动发货完成")
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

    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    resp_params = {
        'jdOrderNo': jd_order_no,
        'agentOrderNo': order_no,
        'produceStatus': 3,
        'code': 'JDO_201',
        'signType': 'MD5',
        'timestamp': timestamp,
    }
    if shop.general_md5_secret:
        sign_p = {k: v for k, v in resp_params.items()
                  if k not in ('sign', 'signType') and v is not None and str(v) != ''}
        resp_params['sign'] = generate_general_sign(sign_p, shop.general_md5_secret)
    return jsonify(resp_params)


@jd_general_api_bp.route('/query', methods=['POST', 'GET'])
def general_query():
    """通用交易 - 反查订单接口"""
    if request.method == 'GET':
        data = request.args.to_dict()
    else:
        data = request.form.to_dict()
        if not data:
            data = request.get_json(silent=True) or {}

    if not data:
        return jsonify(success=False, code=1, message='无效请求数据'), 400

    jd_order_no = (data.get('jdOrderNo') or data.get('jdOrderId') or
                   data.get('jd_order_no') or data.get('orderId') or '')
    if not jd_order_no:
        return jsonify(success=False, code=1, message='缺少订单号'), 400

    order = Order.query.filter_by(jd_order_no=jd_order_no).first()
    if not order:
        return jsonify(success=False, code=1, message='订单不存在')

    # 状态映射：订单状态 -> produceStatus 和 code
    status_to_produce = {0: 3, 1: 3, 2: 1, 3: 2, 4: 2}
    status_to_code = {0: 'JDO_201', 1: 'JDO_201', 2: 'JDO_200', 3: 'JDO_302', 4: 'JDO_302'}
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')

    resp_params = {
        'jdOrderNo': order.jd_order_no,
        'agentOrderNo': order.order_no,
        'produceStatus': status_to_produce.get(order.order_status, 3),
        'code': status_to_code.get(order.order_status, 'JDO_201'),
        'signType': 'MD5',
        'timestamp': timestamp,
    }

    if order.order_status == 2 and order.card_info_parsed:
        from app.services.jd_general import _normalize_cards_for_general, _aes_encrypt
        jd_cards = _normalize_cards_for_general(order.card_info_parsed)
        product_json = json.dumps(jd_cards, ensure_ascii=False)
        shop = order.shop
        if shop and shop.general_aes_secret:
            resp_params['product'] = _aes_encrypt(product_json, shop.general_aes_secret)
        else:
            resp_params['product'] = product_json

    if order.shop and order.shop.general_md5_secret:
        sign_p = {k: v for k, v in resp_params.items()
                  if k not in ('sign', 'signType') and v is not None and str(v) != ''}
        resp_params['sign'] = generate_general_sign(sign_p, order.shop.general_md5_secret)

    return jsonify(resp_params)
