import json
import logging
import uuid
from datetime import datetime
from app.extensions import db
from app.models.order import Order
from app.utils.crypto import base64_encode

logger = logging.getLogger(__name__)


def process_game_direct_order(shop, order_data, customer_id):
    """
    处理游戏点卡直充订单
    返回 (order, is_new) 元组
    """
    order_id = str(order_data.get('orderId', ''))

    # 防重检查
    existing = Order.query.filter_by(order_id=order_id).first()
    if existing:
        return existing, False

    order = Order(
        order_id=order_id,
        shop_id=shop.id,
        shop_type=1,
        order_type=1,
        order_status=0,
        customer_id=customer_id,
        game_account=order_data.get('gameAccount', ''),
        sku_id=str(order_data.get('skuId', '')),
        brand_id=str(order_data.get('brandId', '')),
        buy_num=int(order_data.get('buyNum', 1)),
        total_price=float(order_data.get('totalPrice', 0)),
        raw_data=json.dumps(order_data, ensure_ascii=False),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.session.add(order)
    db.session.commit()
    return order, True


def process_game_card_order(shop, order_data, customer_id):
    """
    处理游戏点卡卡密订单
    返回 (order, is_new) 元组
    """
    order_id = str(order_data.get('orderId', ''))

    # 防重检查
    existing = Order.query.filter_by(order_id=order_id).first()
    if existing:
        return existing, False

    order = Order(
        order_id=order_id,
        shop_id=shop.id,
        shop_type=1,
        order_type=2,
        order_status=0,
        customer_id=customer_id,
        sku_id=str(order_data.get('skuId', '')),
        brand_id=str(order_data.get('brandId', '')),
        buy_num=int(order_data.get('buyNum', 1)),
        total_price=float(order_data.get('totalPrice', 0)),
        raw_data=json.dumps(order_data, ensure_ascii=False),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.session.add(order)
    db.session.commit()
    return order, True


def auto_deliver_direct(shop, order):
    """假发货：直充订单直接回调成功"""
    from app.services.callback_service import callback_game_success
    order.order_status = 2
    db.session.commit()
    callback_game_success(shop, order)


def auto_deliver_card(shop, order):
    """假发货：卡密订单自动生成随机卡密并回调成功"""
    from app.services.callback_service import callback_game_success
    # 生成假卡密
    card_infos = []
    for _ in range(order.buy_num or 1):
        card_infos.append({
            "cardNo": str(uuid.uuid4()).replace('-', '')[:16].upper(),
            "cardPass": str(uuid.uuid4()).replace('-', '')[:16].upper()
        })
    order.order_status = 2
    order.card_info = json.dumps(card_infos, ensure_ascii=False)
    db.session.commit()
    callback_game_success(shop, order, card_infos=card_infos)
