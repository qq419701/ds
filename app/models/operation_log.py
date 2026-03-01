from datetime import datetime
from app.extensions import db


class OperationLog(db.Model):
    __tablename__ = 'operation_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    username = db.Column(db.String(50), nullable=False, comment='操作人用户名')
    action = db.Column(db.String(50), nullable=False, comment='操作类型')
    target_type = db.Column(db.String(50), comment='操作对象类型')
    target_id = db.Column(db.Integer, comment='操作对象ID')
    detail = db.Column(db.Text, comment='操作详情')
    ip_address = db.Column(db.String(50), comment='操作IP')
    create_time = db.Column(db.DateTime, default=datetime.now)
