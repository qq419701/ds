from datetime import datetime
from app.extensions import db


class NotificationLog(db.Model):
    __tablename__ = 'notification_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, comment='订单ID')
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, comment='店铺ID')

    notify_type = db.Column(db.String(20), nullable=False, comment='通知类型：dingtalk/wecom')
    notify_status = db.Column(db.SmallInteger, default=0, comment='通知状态：0=失败 1=成功')

    request_data = db.Column(db.Text, comment='请求数据')
    response_data = db.Column(db.Text, comment='响应数据')
    error_message = db.Column(db.Text, comment='错误信息')

    create_time = db.Column(db.DateTime, default=datetime.now)

    @property
    def notify_type_label(self):
        return '钉钉' if self.notify_type == 'dingtalk' else '企业微信'

    @property
    def status_label(self):
        return '成功' if self.notify_status == 1 else '失败'

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'shop_id': self.shop_id,
            'notify_type': self.notify_type,
            'notify_type_label': self.notify_type_label,
            'notify_status': self.notify_status,
            'status_label': self.status_label,
            'error_message': self.error_message,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }
