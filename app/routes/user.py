from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models.user import User, UserShopPermission
from app.models.shop import Shop
import logging

logger = logging.getLogger(__name__)
user_bp = Blueprint('user', __name__)


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


@user_bp.route('/')
@login_required
@admin_required
def user_list():
    users = User.query.order_by(User.id.asc()).all()
    return render_template('user/list.html', users=users)


@user_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def user_create():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        name = request.form.get('name', '').strip()
        role = request.form.get('role', 'operator')

        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'danger')
        elif not username or not password:
            flash('用户名和密码不能为空', 'danger')
        else:
            user = User(
                username=username,
                name=name,
                role=role,
                can_view_order=int(request.form.get('can_view_order', 1)),
                can_deliver=int(request.form.get('can_deliver', 0)),
                can_refund=int(request.form.get('can_refund', 0)),
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            # Assign shop permissions
            shop_ids = request.form.getlist('shop_ids')
            for sid in shop_ids:
                perm = UserShopPermission(user_id=user.id, shop_id=int(sid))
                db.session.add(perm)
            db.session.commit()

            flash('用户创建成功', 'success')
            _log_operation('create_user', 'user', user.id, f'创建用户: {user.username}')
            return redirect(url_for('user.user_list'))

    shops = Shop.query.order_by(Shop.shop_name).all()
    return render_template('user/form.html', user=None, shops=shops)


@user_bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def user_edit(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('用户不存在', 'danger')
        return redirect(url_for('user.user_list'))

    if request.method == 'POST':
        user.name = request.form.get('name', '').strip()
        user.role = request.form.get('role', 'operator')
        user.can_view_order = int(request.form.get('can_view_order', 1))
        user.can_deliver = int(request.form.get('can_deliver', 0))
        user.can_refund = int(request.form.get('can_refund', 0))
        user.is_active_flag = int(request.form.get('is_active', 1))

        new_password = request.form.get('password', '').strip()
        if new_password:
            user.set_password(new_password)

        # Update shop permissions
        UserShopPermission.query.filter_by(user_id=user.id).delete()
        shop_ids = request.form.getlist('shop_ids')
        for sid in shop_ids:
            perm = UserShopPermission(user_id=user.id, shop_id=int(sid))
            db.session.add(perm)

        db.session.commit()
        _log_operation('edit_user', 'user', user.id, f'编辑用户: {user.username}')
        flash('用户更新成功', 'success')
        return redirect(url_for('user.user_list'))

    shops = Shop.query.order_by(Shop.shop_name).all()
    user_shop_ids = [p.shop_id for p in user.shop_permissions.all()]
    return render_template('user/form.html', user=user, shops=shops, user_shop_ids=user_shop_ids)


@user_bp.route('/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def user_delete(user_id):
    user = db.session.get(User, user_id)
    if user:
        if user.id == current_user.id:
            flash('不能删除当前登录用户', 'danger')
        else:
            uname = user.username
            uid = user.id
            db.session.delete(user)
            db.session.commit()
            _log_operation('delete_user', 'user', uid, f'删除用户: {uname}')
            flash('用户已删除', 'success')
    return redirect(url_for('user.user_list'))
