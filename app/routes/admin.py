import json
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, login_user, logout_user, current_user
from app.extensions import db, login_manager
from app.models.order import Order
from app.models.shop import Shop

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)


class AdminUser:
    """简单管理员用户（不使用数据库）"""
    def __init__(self):
        self.id = 1
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False

    def get_id(self):
        return str(self.id)


@login_manager.user_loader
def load_user(user_id):
    if user_id == '1':
        return AdminUser()
    return None


@admin_bp.route('/')
@login_required
def index():
    """后台首页"""
    total_orders = Order.query.count()
    pending_orders = Order.query.filter_by(order_status=0).count()
    completed_orders = Order.query.filter_by(order_status=2).count()
    refunded_orders = Order.query.filter_by(order_status=4).count()
    return render_template('admin/index.html',
                         total_orders=total_orders,
                         pending_orders=pending_orders,
                         completed_orders=completed_orders,
                         refunded_orders=refunded_orders)


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """管理员登录"""
    import os
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        if username == 'admin' and password == admin_password:
            user = AdminUser()
            login_user(user)
            return redirect(url_for('admin.index'))
        flash('用户名或密码错误', 'error')
    return render_template('admin/login.html')


@admin_bp.route('/logout')
@login_required
def logout():
    """退出登录"""
    logout_user()
    return redirect(url_for('admin.login'))


@admin_bp.route('/orders')
@login_required
def order_list():
    """订单列表"""
    page = request.args.get('page', 1, type=int)
    shop_type = request.args.get('shop_type', 0, type=int)
    order_status = request.args.get('order_status', -1, type=int)
    keyword = request.args.get('keyword', '')

    query = Order.query
    if shop_type:
        query = query.filter_by(shop_type=shop_type)
    if order_status >= 0:
        query = query.filter_by(order_status=order_status)
    if keyword:
        query = query.filter(Order.order_id.contains(keyword))

    orders = query.order_by(Order.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/order_list.html', orders=orders,
                         shop_type=shop_type, order_status=order_status, keyword=keyword)


@admin_bp.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    """订单详情"""
    order = Order.query.get_or_404(order_id)
    shop = Shop.query.get(order.shop_id)
    return render_template('admin/order_detail.html', order=order, shop=shop)


@admin_bp.route('/orders/<int:order_id>/success', methods=['POST'])
@login_required
def order_success(order_id):
    """手动通知成功（直充）"""
    order = Order.query.get_or_404(order_id)
    shop = Shop.query.get(order.shop_id)

    order.order_status = 2
    order.updated_at = datetime.utcnow()
    db.session.commit()

    if order.shop_type == 1:
        from app.services.callback_service import callback_game_success
        success, result = callback_game_success(shop, order)
    else:
        from app.services.callback_service import callback_general_success
        success, result = callback_general_success(shop, order)

    if success:
        flash('回调成功', 'success')
    else:
        flash(f'回调失败: {result}', 'error')

    return redirect(url_for('admin.order_detail', order_id=order_id))


@admin_bp.route('/orders/<int:order_id>/card', methods=['POST'])
@login_required
def order_send_card(order_id):
    """手动发卡密"""
    order = Order.query.get_or_404(order_id)
    shop = Shop.query.get(order.shop_id)

    card_info_str = request.form.get('card_info', '')
    try:
        card_infos = json.loads(card_info_str)
    except Exception:
        flash('卡密格式错误', 'error')
        return redirect(url_for('admin.order_detail', order_id=order_id))

    order.order_status = 2
    order.card_info = card_info_str
    order.updated_at = datetime.utcnow()
    db.session.commit()

    from app.services.callback_service import callback_game_success
    success, result = callback_game_success(shop, order, card_infos=card_infos)

    if success:
        flash('卡密发送成功', 'success')
    else:
        flash(f'回调失败: {result}', 'error')

    return redirect(url_for('admin.order_detail', order_id=order_id))


@admin_bp.route('/orders/<int:order_id>/refund', methods=['POST'])
@login_required
def order_refund(order_id):
    """手动通知退款"""
    order = Order.query.get_or_404(order_id)
    shop = Shop.query.get(order.shop_id)

    order.order_status = 4
    order.updated_at = datetime.utcnow()
    db.session.commit()

    if order.shop_type == 1:
        from app.services.callback_service import callback_game_refund
        success, result = callback_game_refund(shop, order)
    else:
        from app.services.callback_service import callback_general_refund
        success, result = callback_general_refund(shop, order)

    if success:
        flash('退款回调成功', 'success')
    else:
        flash(f'退款回调失败: {result}', 'error')

    return redirect(url_for('admin.order_detail', order_id=order_id))
