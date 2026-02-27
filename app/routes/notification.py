from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models.notification_log import NotificationLog
from app.models.shop import Shop
from app.services.notification import resend_notification

notification_bp = Blueprint('notification', __name__)


def admin_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            return jsonify(success=False, message='无权限'), 403
        return f(*args, **kwargs)
    return decorated


@notification_bp.route('/')
@login_required
@admin_required
def log_list():
    page = request.args.get('page', 1, type=int)
    per_page = 20

    query = NotificationLog.query

    shop_id = request.args.get('shop_id', type=int)
    notify_type = request.args.get('notify_type', '').strip()
    notify_status = request.args.get('notify_status', type=int)

    if shop_id:
        query = query.filter(NotificationLog.shop_id == shop_id)
    if notify_type:
        query = query.filter(NotificationLog.notify_type == notify_type)
    if notify_status is not None and notify_status != -1:
        query = query.filter(NotificationLog.notify_status == notify_status)

    pagination = query.order_by(NotificationLog.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    logs = pagination.items

    shops = Shop.query.order_by(Shop.shop_name).all()
    return render_template('notification/list.html', logs=logs, pagination=pagination, shops=shops)


@notification_bp.route('/resend', methods=['POST'])
@login_required
@admin_required
def resend():
    data = request.get_json()
    log_id = data.get('log_id')
    if not log_id:
        return jsonify(success=False, message='缺少日志ID')

    ok, msg = resend_notification(log_id)
    return jsonify(success=ok, message=msg)


@notification_bp.route('/detail/<int:log_id>')
@login_required
@admin_required
def log_detail(log_id):
    log = db.session.get(NotificationLog, log_id)
    if not log:
        return jsonify(success=False, message='记录不存在'), 404
    return jsonify(log.to_dict())
