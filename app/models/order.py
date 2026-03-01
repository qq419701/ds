import json
from datetime import datetime
from app.extensions import db


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_no = db.Column(db.String(64), unique=True, nullable=False, comment='我方订单号')
    jd_order_no = db.Column(db.String(64), nullable=False, comment='京东订单号')

    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, comment='店铺ID')
    shop_type = db.Column(db.SmallInteger, nullable=False, comment='店铺类型：1=游戏点卡 2=通用交易')
    order_type = db.Column(db.SmallInteger, nullable=False, comment='订单类型：1=直充 2=卡密')

    order_status = db.Column(db.SmallInteger, default=0, comment='订单状态：0=待支付 1=处理中 2=已完成 3=已取消')

    sku_id = db.Column(db.String(64), comment='商品SKU')
    product_info = db.Column(db.Text, comment='商品信息')
    amount = db.Column(db.Integer, nullable=False, comment='金额（分）')
    quantity = db.Column(db.Integer, default=1, comment='数量')

    produce_account = db.Column(db.String(255), comment='充值账号')

    card_info = db.Column(db.Text, comment='卡密信息JSON')

    notify_url = db.Column(db.String(500), comment='回调地址')
    notify_status = db.Column(db.SmallInteger, default=0, comment='回调状态：0=未回调 1=成功 2=失败')
    notify_time = db.Column(db.DateTime, comment='回调时间')

    notified = db.Column(db.SmallInteger, default=0, comment='是否已发送通知：0=否 1=是')
    notify_send_time = db.Column(db.DateTime, comment='通知发送时间')

    pay_time = db.Column(db.DateTime, comment='支付时间')
    deliver_time = db.Column(db.DateTime, comment='发货时间')

    remark = db.Column(db.String(500), comment='备注')
    create_time = db.Column(db.DateTime, default=datetime.now)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    notification_logs = db.relationship('NotificationLog', backref='order', lazy='dynamic')

    STATUS_MAP = {0: '待支付', 1: '处理中', 2: '已完成', 3: '已取消', 4: '已退款', 5: '异常'}
    TYPE_MAP = {1: '直充', 2: '卡密'}
    SHOP_TYPE_MAP = {1: '游戏点卡', 2: '通用交易'}

    __table_args__ = (
        db.Index('idx_jd_order_shop', 'jd_order_no', 'shop_id', unique=True),
    )

    @property
    def order_status_label(self):
        return self.STATUS_MAP.get(self.order_status, '未知')

    @property
    def order_type_label(self):
        return self.TYPE_MAP.get(self.order_type, '未知')

    @property
    def shop_type_label(self):
        return self.SHOP_TYPE_MAP.get(self.shop_type, '未知')

    @property
    def amount_yuan(self):
        return f'{self.amount / 100:.2f}'

    @property
    def card_info_parsed(self):
        if self.card_info:
            try:
                return json.loads(self.card_info)
            except (json.JSONDecodeError, TypeError):
                return []
        return []


    def set_card_info(self, cards):
        """设置卡密信息"""
        if cards:
            self.card_info = json.dumps(cards, ensure_ascii=False)
        else:
            self.card_info = None

    def to_dict(self):
        return {
            'id': self.id,
            'order_no': self.order_no,
            'jd_order_no': self.jd_order_no,
            'shop_id': self.shop_id,
            'shop_type': self.shop_type,
            'order_type': self.order_type,
            'order_status': self.order_status,
            'order_status_label': self.order_status_label,
            'order_type_label': self.order_type_label,
            'sku_id': self.sku_id,
            'product_info': self.product_info,
            'amount': self.amount,
            'amount_yuan': self.amount_yuan,
            'quantity': self.quantity,
            'produce_account': self.produce_account,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }
