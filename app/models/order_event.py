"""订单事件日志模型。

记录订单生命周期内的各种事件，包括：
- 订单创建
- 状态变更
- 91卡券提卡记录
- 直充API调用记录
- 手动操作记录
- 回调通知记录
"""
from datetime import datetime
from app.extensions import db


class OrderEvent(db.Model):
    """订单事件日志表。

    每当订单发生重要变化时（状态变更、发货、回调等）记录一条事件。
    在订单详情弹窗中按时间倒序展示。
    """
    __tablename__ = 'order_events'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # 关联订单
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'),
                          nullable=False, comment='订单ID')
    order_no = db.Column(db.String(64), comment='系统订单号（冗余，方便查询）')

    # 事件类型：order_created=订单创建 status_changed=状态变更
    # card91_fetch=91卡券提卡 card91_deliver=91卡券发卡
    # manual_deliver=手动发卡 notify_success=通知成功
    # notify_refund=通知退款 callback_received=收到回调
    event_type = db.Column(db.String(50), nullable=False, comment='事件类型')
    event_desc = db.Column(db.String(500), comment='事件描述')

    # 额外数据（JSON格式，记录详细信息）
    event_data = db.Column(db.Text, comment='事件详细数据JSON')

    # 操作人（系统自动触发则为空）
    operator = db.Column(db.String(100), comment='操作人（手动操作时记录）')

    # 事件结果：success=成功 failed=失败 info=信息
    result = db.Column(db.String(20), default='info', comment='事件结果：success/failed/info')

    create_time = db.Column(db.DateTime, default=datetime.utcnow, comment='事件发生时间（UTC）')

    # 关联关系
    order = db.relationship('Order', backref=db.backref('events', lazy='dynamic',
                                                         order_by='OrderEvent.create_time.desc()'))

    # 事件类型标签
    EVENT_TYPE_LABELS = {
        'order_created': '📦 订单创建',
        'status_changed': '🔄 状态变更',
        'card91_fetch': '🎫 91卡券提卡',
        'card91_deliver': '✅ 91卡券发卡',
        'manual_deliver': '👋 手动发卡',
        'notify_success': '✅ 通知成功',
        'notify_refund': '💰 通知退款',
        'callback_received': '📡 收到回调',
        'direct_charge': '⚡ 直充发货',
        'error': '❌ 错误',
    }

    @property
    def event_type_label(self):
        """事件类型中文标签"""
        return self.EVENT_TYPE_LABELS.get(self.event_type, self.event_type)

    @property
    def create_time_beijing(self):
        """北京时间（UTC+8）"""
        if self.create_time:
            from datetime import timezone, timedelta
            bj_tz = timezone(timedelta(hours=8))
            return self.create_time.replace(tzinfo=timezone.utc).astimezone(bj_tz)
        return None

    def to_dict(self):
        """转换为字典"""
        import json
        bj_time = self.create_time_beijing
        try:
            data = json.loads(self.event_data) if self.event_data else {}
        except Exception:
            data = {}
        return {
            'id': self.id,
            'order_id': self.order_id,
            'event_type': self.event_type,
            'event_type_label': self.event_type_label,
            'event_desc': self.event_desc or '',
            'event_data': data,
            'operator': self.operator or '系统',
            'result': self.result,
            'create_time': bj_time.strftime('%Y-%m-%d %H:%M:%S') if bj_time else '',
        }
