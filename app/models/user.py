from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False, comment='用户名')
    password_hash = db.Column(db.String(255), nullable=False, comment='密码哈希')
    name = db.Column(db.String(100), comment='姓名')

    role = db.Column(db.String(20), nullable=False, default='operator', comment='角色：admin=管理员 operator=操作员')

    can_view_order = db.Column(db.SmallInteger, default=1, comment='查看订单权限')
    can_deliver = db.Column(db.SmallInteger, default=0, comment='发货权限')
    can_refund = db.Column(db.SmallInteger, default=0, comment='退款权限')

    is_active_flag = db.Column('is_active', db.SmallInteger, default=1, comment='是否激活')
    last_login = db.Column(db.DateTime, comment='最后登录时间')
    last_login_ip = db.Column(db.String(50), comment='最后登录IP')
    login_fail_count = db.Column(db.Integer, default=0, comment='连续登录失败次数')
    locked_until = db.Column(db.DateTime, nullable=True, comment='锁定截止时间')

    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    shop_permissions = db.relationship('UserShopPermission', backref='user', lazy='dynamic',
                                       cascade='all, delete-orphan')

    @property
    def is_active(self):
        return self.is_active_flag == 1

    @property
    def is_admin(self):
        return self.role == 'admin'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_permitted_shop_ids(self):
        if self.is_admin:
            return None  # admin can see all
        return [p.shop_id for p in self.shop_permissions.all()]

    def has_shop_permission(self, shop_id):
        if self.is_admin:
            return True
        return self.shop_permissions.filter_by(shop_id=shop_id).first() is not None

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'role': self.role,
            'can_view_order': self.can_view_order,
            'can_deliver': self.can_deliver,
            'can_refund': self.can_refund,
            'is_active': self.is_active_flag,
            'last_login': self.last_login.strftime('%Y-%m-%d %H:%M:%S') if self.last_login else None,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }


class UserShopPermission(db.Model):
    __tablename__ = 'user_shop_permissions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='用户ID')
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, comment='店铺ID')

    create_time = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'shop_id', name='uk_user_shop'),
    )
