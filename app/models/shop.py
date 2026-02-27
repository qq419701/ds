from app.extensions import db
from datetime import datetime


class Shop(db.Model):
    """店铺配置模型"""
    __tablename__ = 'shops'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 店铺名称

    # 游戏点卡配置
    game_customer_id = db.Column(db.String(50))
    game_md5_secret = db.Column(db.String(100))
    game_api_url = db.Column(db.String(200))               # 通用回调URL
    game_direct_callback_url = db.Column(db.String(200))   # 直充专用回调URL
    game_card_callback_url = db.Column(db.String(200))     # 卡密专用回调URL

    # 通用交易配置
    general_vendor_id = db.Column(db.String(50))
    general_md5_secret = db.Column(db.String(100))
    general_aes_secret = db.Column(db.String(100))
    general_callback_url = db.Column(db.String(200))

    # 阿奇索配置
    agiso_enabled = db.Column(db.Integer, default=0)       # 0=禁用 1=启用
    agiso_app_id = db.Column(db.String(50))
    agiso_app_secret = db.Column(db.String(100))
    agiso_access_token = db.Column(db.String(200))
    agiso_host = db.Column(db.String(100))
    agiso_port = db.Column(db.String(10))

    # 其他配置
    auto_deliver = db.Column(db.Integer, default=0)        # 假发货模式 0=禁用 1=启用
    default_address = db.Column(db.Text)                   # 默认地址JSON

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = db.relationship('Order', backref='shop', lazy=True)

    def __repr__(self):
        return f'<Shop {self.name}>'
