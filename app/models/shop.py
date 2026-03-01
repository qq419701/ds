from datetime import datetime
from app.extensions import db


class Shop(db.Model):
    __tablename__ = 'shops'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    shop_name = db.Column(db.String(100), nullable=False, comment='店铺名称')
    shop_code = db.Column(db.String(50), unique=True, nullable=False, comment='店铺代码')
    shop_type = db.Column(db.SmallInteger, nullable=False, comment='店铺类型：1=游戏点卡 2=通用交易')

    # 游戏点卡配置
    game_customer_id = db.Column(db.String(50), comment='游戏点卡客户ID')
    game_md5_secret = db.Column(db.String(500), comment='游戏点卡MD5密钥')
    game_direct_callback_url = db.Column(db.String(500), comment='游戏直充回调地址')
    game_card_callback_url = db.Column(db.String(500), comment='游戏卡密回调地址')
    game_api_url = db.Column(db.String(500), comment='游戏点卡接口地址')

    # 通用交易配置
    general_vendor_id = db.Column(db.String(50), comment='通用交易商家ID')
    general_md5_secret = db.Column(db.String(500), comment='通用交易MD5密钥')
    general_aes_secret = db.Column(db.String(500), comment='通用交易AES密钥')
    general_callback_url = db.Column(db.String(500), comment='通用交易回调地址')
    general_api_url = db.Column(db.String(500), comment='通用交易接口地址')

    # 阿奇索配置（已废弃，保留字段兼容旧数据）
    agiso_enabled = db.Column(db.SmallInteger, default=0, comment='阿奇索已废弃')
    agiso_host = db.Column(db.String(100), comment='阿奇索已废弃')
    agiso_port = db.Column(db.Integer, comment='阿奇索已废弃')
    agiso_app_id = db.Column(db.String(100), comment='阿奇索已废弃')
    agiso_app_secret = db.Column(db.String(500), comment='阿奇索已废弃')
    agiso_access_token = db.Column(db.String(500), comment='阿奇索已废弃')

    # 91卡券配置（每个店铺单独配置）
    card91_api_url = db.Column(db.String(500), comment='91卡券API地址')
    card91_api_key = db.Column(db.String(200), comment='91卡券API密钥')
    card91_api_secret = db.Column(db.String(500), comment='91卡券API签名密钥')

    # 订单通知配置
    notify_enabled = db.Column(db.SmallInteger, default=0, comment='是否启用订单通知：0=否 1=是')
    dingtalk_webhook = db.Column(db.String(500), comment='钉钉机器人Webhook地址')
    dingtalk_secret = db.Column(db.String(500), comment='钉钉机器人加签密钥')
    wecom_webhook = db.Column(db.String(500), comment='企业微信机器人Webhook地址')

    # 发货方式（已废弃，默认全部手动发货）
    auto_deliver = db.Column(db.SmallInteger, default=0, comment='发货方式已废弃，保留字段兼容旧数据')

    # 店铺状态
    is_enabled = db.Column(db.SmallInteger, default=1, comment='是否启用：0=禁用 1=启用')
    expire_time = db.Column(db.DateTime, comment='到期时间')
    remark = db.Column(db.String(500), comment='备注')

    create_time = db.Column(db.DateTime, default=datetime.now)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    orders = db.relationship('Order', backref='shop', lazy='dynamic')
    notification_logs = db.relationship('NotificationLog', backref='shop', lazy='dynamic')

    @property
    def shop_type_label(self):
        return '游戏点卡' if self.shop_type == 1 else '通用交易'

    @property
    def status_label(self):
        return '启用' if self.is_enabled == 1 else '禁用'

    @property
    def notify_status_label(self):
        return '已启用' if self.notify_enabled == 1 else '未启用'

    def to_dict(self):
        return {
            'id': self.id,
            'shop_name': self.shop_name,
            'shop_code': self.shop_code,
            'shop_type': self.shop_type,
            'shop_type_label': self.shop_type_label,
            'is_enabled': self.is_enabled,
            'notify_enabled': self.notify_enabled,
            'expire_time': self.expire_time.strftime('%Y-%m-%d %H:%M:%S') if self.expire_time else None,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }
