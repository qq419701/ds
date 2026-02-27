import json
import logging
import uuid
from datetime import datetime
from app.extensions import db
from app.models.order import Order

logger = logging.getLogger(__name__)


def process_general_order(shop, form_data):
    """
    处理通用交易接单
    返回 (order, is_new) 元组
    """
    jd_order_no = str(form_data.get('jdOrderNo', ''))

    # 防重检查
    existing = Order.query.filter_by(jd_order_no=jd_order_no).first()
    if existing:
        return existing, False

    agent_order_no = str(uuid.uuid4()).replace('-', '')[:20]
    notify_url = form_data.get('notifyUrl', '')

    order = Order(
        order_id=jd_order_no,
        shop_id=shop.id,
        shop_type=2,
        order_type=1,
        order_status=1,
        notify_url=notify_url,
        vendor_id=str(form_data.get('vendorId', '')),
        jd_order_no=jd_order_no,
        agent_order_no=agent_order_no,
        produce_account=form_data.get('produceAccount', ''),
        quantity=int(form_data.get('quantity', 1)),
        ware_no=str(form_data.get('wareNo', '')),
        total_price=float(form_data.get('totalPrice', 0)) / 100,
        raw_data=json.dumps(dict(form_data), ensure_ascii=False),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.session.add(order)
    db.session.commit()
    return order, True


def auto_deliver_general(shop, order):
    """假发货：通用交易直接回调成功"""
    from app.services.callback_service import callback_general_success
    order.order_status = 2
    db.session.commit()
    callback_general_success(shop, order)
