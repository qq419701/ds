from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models.shop import Shop
from app.services.notification import send_test_notification
import logging

# 注意：阿奇索（Agiso）相关功能已于2026年删除，系统统一使用91卡券接口。

logger = logging.getLogger(__name__)
shop_bp = Blueprint('shop', __name__)


def admin_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('无权限访问', 'danger')
            return redirect(url_for('order.order_list'))
        return f(*args, **kwargs)
    return decorated


def _log_operation(action, target_type, target_id, detail):
    try:
        from app.models.operation_log import OperationLog
        log = OperationLog(
            user_id=current_user.id,
            username=current_user.username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=request.remote_addr,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.warning(f'记录操作日志失败: {e}')


@shop_bp.route('/')
@login_required
@admin_required
def shop_list():
    shops = Shop.query.order_by(Shop.id.desc()).all()
    return render_template('shop/list.html', shops=shops)


@shop_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def shop_create():
    if request.method == 'POST':
        shop = Shop(
            shop_name=request.form.get('shop_name', '').strip(),
            shop_code=request.form.get('shop_code', '').strip(),
            shop_type=int(request.form.get('shop_type', 1)),
        )
        _fill_shop_fields(shop, request.form)
        db.session.add(shop)
        try:
            db.session.commit()
            _log_operation('create_shop', 'shop', shop.id, f'创建店铺: {shop.shop_name}')
            flash('店铺创建成功', 'success')
            return redirect(url_for('shop.shop_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败：{e}', 'danger')

    return render_template('shop/form.html', shop=None)


@shop_bp.route('/edit/<int:shop_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def shop_edit(shop_id):
    shop = db.session.get(Shop, shop_id)
    if not shop:
        flash('店铺不存在', 'danger')
        return redirect(url_for('shop.shop_list'))

    if request.method == 'POST':
        shop.shop_name = request.form.get('shop_name', '').strip()
        shop.shop_type = int(request.form.get('shop_type', 1))
        _fill_shop_fields(shop, request.form)
        try:
            db.session.commit()
            _log_operation('edit_shop', 'shop', shop.id, f'编辑店铺: {shop.shop_name}')
            flash('店铺更新成功', 'success')
            return redirect(url_for('shop.shop_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败：{e}', 'danger')

    return render_template('shop/form.html', shop=shop)


@shop_bp.route('/delete/<int:shop_id>', methods=['POST'])
@login_required
@admin_required
def shop_delete(shop_id):
    shop = db.session.get(Shop, shop_id)
    if shop:
        shop_name = shop.shop_name
        shop_id = shop.id
        db.session.delete(shop)
        db.session.commit()
        _log_operation('delete_shop', 'shop', shop_id, f'删除店铺: {shop_name}')
        flash('店铺已删除', 'success')
    return redirect(url_for('shop.shop_list'))


@shop_bp.route('/test-notification', methods=['POST'])
@login_required
@admin_required
def test_notification():
    data = request.get_json()
    shop_id = data.get('shop_id')
    notify_type = data.get('notify_type', 'dingtalk')

    shop = db.session.get(Shop, shop_id)
    if not shop:
        return jsonify(success=False, message='店铺不存在')

    ok, msg = send_test_notification(shop, notify_type)
    return jsonify(success=ok, message=msg)


@shop_bp.route('/card91-test/<int:shop_id>', methods=['GET'])
@login_required
@admin_required
def card91_test(shop_id):
    """测试91卡券API连接是否正常。"""
    shop = db.session.get(Shop, shop_id)
    if not shop:
        return jsonify(success=False, message='店铺不存在')
    if not shop.card91_api_key:
        return jsonify(success=False, message='该店铺未配置91卡券API密钥')

    from app.services.card91 import card91_test_connection
    ok, msg = card91_test_connection(shop)
    return jsonify(success=ok, message=msg)


def _fill_shop_fields(shop, form):
    """从表单数据填充店铺字段（已移除阿奇索相关字段）。"""
    # 游戏点卡配置
    shop.game_customer_id = form.get('game_customer_id', '').strip() or None
    shop.game_md5_secret = form.get('game_md5_secret', '').strip() or None
    shop.game_direct_callback_url = form.get('game_direct_callback_url', '').strip() or None
    shop.game_card_callback_url = form.get('game_card_callback_url', '').strip() or None
    shop.game_api_url = form.get('game_api_url', '').strip() or None

    # 通用交易配置
    shop.general_vendor_id = form.get('general_vendor_id', '').strip() or None
    shop.general_md5_secret = form.get('general_md5_secret', '').strip() or None
    shop.general_aes_secret = form.get('general_aes_secret', '').strip() or None
    shop.general_callback_url = form.get('general_callback_url', '').strip() or None
    shop.general_api_url = form.get('general_api_url', '').strip() or None

    # 订单通知配置
    shop.notify_enabled = int(form.get('notify_enabled', 0))
    shop.dingtalk_webhook = form.get('dingtalk_webhook', '').strip() or None
    shop.dingtalk_secret = form.get('dingtalk_secret', '').strip() or None
    shop.wecom_webhook = form.get('wecom_webhook', '').strip() or None

    # 91卡券配置（每个店铺单独配置）
    shop.card91_api_url = form.get('card91_api_url', '').strip() or None
    shop.card91_api_key = form.get('card91_api_key', '').strip() or None
    shop.card91_api_secret = form.get('card91_api_secret', '').strip() or None

    # 店铺状态（默认全部手动发货，不再有自动发货开关）
    shop.is_enabled = int(form.get('is_enabled', 1))
    expire_time_str = form.get('expire_time', '').strip()
    if expire_time_str:
        try:
            shop.expire_time = datetime.strptime(expire_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            try:
                shop.expire_time = datetime.strptime(expire_time_str, '%Y-%m-%d')
            except ValueError:
                pass
    shop.remark = form.get('remark', '').strip() or None
