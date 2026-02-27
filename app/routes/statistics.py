from datetime import datetime, timedelta
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from sqlalchemy import func, text

from app.extensions import db
from app.models.order import Order
from app.models.shop import Shop

statistics_bp = Blueprint('statistics', __name__)


def admin_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            from flask import redirect, url_for, flash
            flash('无权限访问', 'danger')
            return redirect(url_for('order.order_list'))
        return f(*args, **kwargs)
    return decorated


@statistics_bp.route('/')
@login_required
@admin_required
def index():
    # Overall stats
    total_orders = Order.query.count()
    total_amount = db.session.query(func.sum(Order.amount)).scalar() or 0
    completed_orders = Order.query.filter_by(order_status=2).count()
    pending_orders = Order.query.filter(Order.order_status.in_([0, 1])).count()

    # Per-shop stats（含阿奇索启用状态）
    shop_stats = db.session.query(
        Shop.id,
        Shop.shop_name,
        Shop.agiso_enabled,
        func.count(Order.id).label('order_count'),
        func.coalesce(func.sum(Order.amount), 0).label('total_amount'),
    ).outerjoin(Order, Shop.id == Order.shop_id).group_by(Shop.id).all()

    # 订单状态分布
    status_stats = db.session.query(
        Order.order_status,
        func.count(Order.id).label('count'),
    ).group_by(Order.order_status).all()
    status_labels = {0: '待处理', 1: '处理中', 2: '已完成', 3: '已取消', 4: '已退款', 5: '异常'}
    status_distribution = [
        {'name': status_labels.get(s.order_status, '未知'), 'value': s.count}
        for s in status_stats
    ]

    # 近7天统计 - 单条SQL优化
    today = datetime.utcnow().date()
    seven_days_ago = datetime.combine(today - timedelta(days=6), datetime.min.time())
    raw_daily = db.session.query(
        func.date(Order.create_time).label('day'),
        func.count(Order.id).label('count'),
        func.coalesce(func.sum(Order.amount), 0).label('amount'),
    ).filter(Order.create_time >= seven_days_ago).group_by(func.date(Order.create_time)).all()

    daily_map = {str(r.day): {'count': r.count, 'amount': r.amount} for r in raw_daily}
    daily_stats = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        key = str(day)
        rec = daily_map.get(key, {'count': 0, 'amount': 0})
        daily_stats.append({
            'date': day.strftime('%m-%d'),
            'count': rec['count'],
            'amount': rec['amount'] / 100,
        })

    # 店铺订单分布（用于饼图）
    shop_pie = [
        {'name': s.shop_name, 'value': s.order_count}
        for s in shop_stats if s.order_count > 0
    ]

    return render_template('statistics/index.html',
                           total_orders=total_orders,
                           total_amount=total_amount / 100,
                           completed_orders=completed_orders,
                           pending_orders=pending_orders,
                           shop_stats=shop_stats,
                           daily_stats=daily_stats,
                           status_distribution=status_distribution,
                           shop_pie=shop_pie)
