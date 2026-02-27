from datetime import datetime
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models.operation_log import OperationLog

operation_log_bp = Blueprint('operation_log', __name__)


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


@operation_log_bp.route('/')
@login_required
@admin_required
def log_list():
    page = request.args.get('page', 1, type=int)
    per_page = 30

    query = OperationLog.query

    action = request.args.get('action', '').strip()
    username = request.args.get('username', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    if action:
        query = query.filter(OperationLog.action == action)
    if username:
        query = query.filter(OperationLog.username.like(f'%{username}%'))
    if start_date:
        try:
            query = query.filter(OperationLog.create_time >= datetime.strptime(start_date, '%Y-%m-%d'))
        except ValueError:
            pass
    if end_date:
        try:
            query = query.filter(OperationLog.create_time <= datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
        except ValueError:
            pass

    pagination = query.order_by(OperationLog.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    logs = pagination.items

    return render_template('operation_log/list.html', logs=logs, pagination=pagination)
