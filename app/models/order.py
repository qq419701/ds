from app.extensions import db
from datetime import datetime


class Order(db.Model):
    """订单模型"""
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(50), unique=True)       # 京东订单号
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'))
    shop_type = db.Column(db.Integer)   # 1=游戏点卡 2=通用交易
    order_type = db.Column(db.Integer)  # 1=直充 2=卡密
    order_status = db.Column(db.Integer, default=0)
    # 0=待处理 1=处理中 2=已完成 3=已取消 4=已退款

    notify_url = db.Column(db.String(200))          # 通用交易回调地址
    notify_status = db.Column(db.Integer, default=0)  # 0=未回调 1=成功 2=失败
    card_info = db.Column(db.Text)                  # 卡密JSON

    # 游戏点卡字段
    customer_id = db.Column(db.String(50))
    game_account = db.Column(db.String(100))
    sku_id = db.Column(db.String(50))
    brand_id = db.Column(db.String(50))
    buy_num = db.Column(db.Integer)
    total_price = db.Column(db.Float)

    # 通用交易字段
    vendor_id = db.Column(db.String(50))
    jd_order_no = db.Column(db.String(50))
    agent_order_no = db.Column(db.String(50))
    produce_account = db.Column(db.String(100))
    quantity = db.Column(db.Integer)
    ware_no = db.Column(db.String(50))

    raw_data = db.Column(db.Text)    # 原始请求数据
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Order {self.order_id}>'
