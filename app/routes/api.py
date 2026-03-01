"""外部API接口 - 京东平台订单回调及内部API。

支持京东游戏点卡平台和京东通用交易平台的订单接收，
包含MD5签名验证功能。
"""
import json
import logging
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, session

from flask_login import login_required, current_user
from app.extensions import db
from app.models.order import Order
from app.models.shop import Shop
from app.services.notification import send_order_notification, send_test_notification
from app.services.jd_game import verify_game_sign
from app.services.jd_general import verify_general_sign

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


@api_bp.route('/order/create', methods=['POST'])
def create_order():
    """接收京东平台订单。

    支持京东游戏点卡平台和通用交易平台的订单推送。
    根据店铺类型自动选择对应的签名验证方式。
    """
    import json as _json
    req_body = request.get_data(as_text=True)
    req_headers = str(dict(request.headers))

    def _save_api_log(shop_id, response_status, response_body):
        try:
            from app.models.api_log import ApiLog
            log = ApiLog(
                shop_id=shop_id,
                api_type='create_order',
                request_method=request.method,
                request_url=request.url,
                request_headers=req_headers[:2000],
                request_body=req_body[:4000],
                response_status=response_status,
                response_body=str(response_body)[:4000],
                ip_address=request.remote_addr,
            )
            db.session.add(log)
            db.session.commit()
        except Exception as ex:
            logger.warning(f'记录API日志失败: {ex}')

    data = request.get_json()
    if not data:
        resp = jsonify(success=False, message='无效请求数据')
        _save_api_log(None, 400, '无效请求数据')
        return resp, 400

    shop_code = data.get('shop_code')
    shop = Shop.query.filter_by(shop_code=shop_code, is_enabled=1).first()
    if not shop:
        resp = jsonify(success=False, message='店铺不存在或已禁用')
        _save_api_log(None, 400, '店铺不存在或已禁用')
        return resp, 400

    # 检查店铺是否已到期
    if shop.expire_time and shop.expire_time < datetime.now():
        logger.warning("店铺已到期: shop=%s, expire=%s", shop.shop_code, shop.expire_time)
        _save_api_log(shop.id, 403, '店铺已到期')
        return jsonify(success=False, message='店铺已到期'), 403

    # 根据店铺类型验证签名
    if shop.shop_type == 1 and shop.game_md5_secret:
        # 京东游戏点卡平台 - MD5签名验证
        if not verify_game_sign(data, shop.game_md5_secret):
            logger.warning("游戏点卡订单签名验证失败: shop=%s", shop.shop_code)
            _save_api_log(shop.id, 403, '签名验证失败')
            return jsonify(success=False, message='签名验证失败'), 403
    elif shop.shop_type == 2 and shop.general_md5_secret:
        # 京东通用交易平台 - MD5签名验证
        if not verify_general_sign(data, shop.general_md5_secret):
            logger.warning("通用交易订单签名验证失败: shop=%s", shop.shop_code)
            _save_api_log(shop.id, 403, '签名验证失败')
            return jsonify(success=False, message='签名验证失败'), 403

    order_no = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"

    # 防重复：检查相同 jd_order_no + shop_id
    jd_order_no = data.get('jd_order_no', '')
    existing = Order.query.filter_by(jd_order_no=jd_order_no, shop_id=shop.id).first()
    if existing:
        return jsonify(success=False, message='订单已存在，请勿重复提交', order_no=existing.order_no)

    order = Order(
        order_no=order_no,
        jd_order_no=jd_order_no,
        shop_id=shop.id,
        shop_type=shop.shop_type,
        order_type=int(data.get('order_type', 1)),
        order_status=int(data.get('order_status', 0)),
        sku_id=data.get('sku_id'),
        product_info=data.get('product_info'),
        amount=int(data.get('amount', 0)),
        quantity=int(data.get('quantity', 1)),
        produce_account=data.get('produce_account'),
        notify_url=data.get('notify_url'),
    )

    db.session.add(order)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        # 并发情况下可能产生唯一约束冲突，再次查询
        existing = Order.query.filter_by(jd_order_no=jd_order_no, shop_id=shop.id).first()
        if existing:
            return jsonify(success=False, message='订单已存在，请勿重复提交', order_no=existing.order_no)
        _save_api_log(shop.id, 500, '订单创建失败')
        return jsonify(success=False, message='订单创建失败'), 500

    # 记录订单创建事件
    try:
        from app.models.order_event import OrderEvent
        create_event = OrderEvent(
            order_id=order.id,
            order_no=order.order_no,
            event_type='order_created',
            event_desc=f'订单创建，京东订单号：{jd_order_no}，类型：{"直充" if order.order_type==1 else "卡密"}',
            result='info',
        )
        db.session.add(create_event)
        db.session.commit()
    except Exception as e:
        logger.warning(f"记录订单创建事件失败: {e}")

    # 91卡券自动发货（卡密订单，根据商品配置deliver_type=1时自动提卡）
    if order.order_type == 2:
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
                from app.services.jd_game import callback_game_card_deliver
                from app.services.jd_general import callback_general_card_deliver
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
                    if shop.shop_type == 1:
                        success, callback_msg = callback_game_card_deliver(shop, order, cards)
                    else:
                        success, callback_msg = callback_general_card_deliver(shop, order, cards)
                    if success:
                        order.order_status = 2
                        order.notify_status = 1
                        order.notify_time = datetime.now()
                db.session.commit()
        except Exception as e:
            logger.error(f"91卡券自动发货失败: {e}")

    # 如果店铺启用了通知，发送订单通知
    try:
        send_order_notification(order, shop)
    except Exception:
        pass  # 通知失败不影响订单创建

    _save_api_log(shop.id, 200, f'订单创建成功: {order_no}')
    return jsonify(success=True, message='订单创建成功', order_no=order_no)


@api_bp.route('/shop/test-notification', methods=['POST'])
@login_required
def api_test_notification():
    """Send test notification for a shop."""
    data = request.get_json()
    if not data:
        return jsonify(success=False, message='无效请求数据'), 400

    shop_id = data.get('shop_id')
    notify_type = data.get('notify_type', 'dingtalk')

    shop = db.session.get(Shop, shop_id)
    if not shop:
        return jsonify(success=False, message='店铺不存在')

    ok, msg = send_test_notification(shop, notify_type)
    return jsonify(success=ok, message=msg)


@api_bp.route('/notification/resend', methods=['POST'])
@login_required
def api_resend_notification():
    """Resend a notification."""
    from app.services.notification import resend_notification

    data = request.get_json()
    log_id = data.get('log_id')
    if not log_id:
        return jsonify(success=False, message='缺少日志ID')

    ok, msg = resend_notification(log_id)
    return jsonify(success=ok, message=msg)


@api_bp.route('/new-order-count', methods=['GET'])
@login_required
def new_order_count():
    """返回当前用户权限范围内的新订单数量（用于声音提醒）"""
    from datetime import timedelta
    # 从session获取上次检查时间，默认15秒前
    last_check_key = 'last_order_check'
    last_check = session.get(last_check_key)
    now = datetime.now()
    if last_check:
        try:
            last_check = datetime.fromisoformat(last_check)
        except (ValueError, TypeError):
            last_check = now - timedelta(seconds=15)
    else:
        last_check = now - timedelta(seconds=15)

    # 更新检查时间
    session[last_check_key] = now.isoformat()

    query = Order.query.filter(Order.create_time > last_check)
    if not current_user.is_admin:
        permitted_ids = current_user.get_permitted_shop_ids()
        if permitted_ids:
            query = query.filter(Order.shop_id.in_(permitted_ids))
        else:
            return jsonify(count=0)

    count = query.count()
    # 未处理订单数
    pending_query = Order.query.filter(Order.order_status.in_([0, 1]))
    if not current_user.is_admin:
        permitted_ids = current_user.get_permitted_shop_ids()
        if permitted_ids:
            pending_query = pending_query.filter(Order.shop_id.in_(permitted_ids))
        else:
            return jsonify(count=count, pending=0)
    pending = pending_query.count()
    return jsonify(count=count, pending=pending)
