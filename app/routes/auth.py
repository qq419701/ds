from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models.user import User
from app.utils.captcha import generate_captcha

auth_bp = Blueprint('auth', __name__)

LOCK_MINUTES = 15
MAX_FAIL = 3


@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('order.order_list'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/captcha')
def captcha():
    """生成验证码"""
    code, img_data = generate_captcha()
    session['captcha_code'] = code.upper()
    return jsonify(image=img_data)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('order.order_list'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        captcha_input = request.form.get('captcha', '').strip().upper()

        # 验证码校验（TESTING模式跳过）
        from flask import current_app
        if not current_app.config.get('TESTING'):
            captcha_code = session.get('captcha_code', '')
            if not captcha_code or captcha_input != captcha_code:
                session.pop('captcha_code', None)
                flash('验证码错误', 'danger')
                return render_template('auth/login.html')
            session.pop('captcha_code', None)

        user = User.query.filter_by(username=username).first()

        if user:
            # 检查账户是否锁定
            if user.locked_until and user.locked_until > datetime.now():
                remaining = int((user.locked_until - datetime.now()).total_seconds() / 60) + 1
                flash(f'账户已锁定，请{remaining}分钟后再试', 'danger')
                return render_template('auth/login.html')

            if user.check_password(password) and user.is_active:
                # 登录成功，重置失败计数
                user.login_fail_count = 0
                user.locked_until = None
                user.last_login = datetime.now()
                user.last_login_ip = request.remote_addr
                db.session.commit()

                # 记录登录日志
                try:
                    from app.models.operation_log import OperationLog
                    log = OperationLog(
                        user_id=user.id,
                        username=user.username,
                        action='login',
                        target_type='user',
                        target_id=user.id,
                        detail=f'用户 {user.username} 登录成功',
                        ip_address=request.remote_addr,
                    )
                    db.session.add(log)
                    db.session.commit()
                except Exception:
                    pass

                login_user(user)
                next_page = request.args.get('next')
                return redirect(next_page or url_for('order.order_list'))
            else:
                # 登录失败
                user.login_fail_count = (user.login_fail_count or 0) + 1
                if user.login_fail_count >= MAX_FAIL:
                    user.locked_until = datetime.now() + timedelta(minutes=LOCK_MINUTES)
                    user.login_fail_count = 0
                    db.session.commit()
                    flash(f'连续登录失败次数过多，账户已锁定{LOCK_MINUTES}分钟', 'danger')
                else:
                    db.session.commit()
                    flash(f'用户名或密码错误（还剩{MAX_FAIL - user.login_fail_count}次）', 'danger')
        else:
            flash('用户名或密码错误', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
