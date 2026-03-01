"""商品管理模型。

每个商品可绑定一个店铺，并配置对应的发货方式（91卡券卡密 / 直充预留）。
商品维度：一个SKU对应一个发货配置。
"""
from datetime import datetime
from app.extensions import db


class Product(db.Model):
    """商品配置表。

    用于记录店铺商品信息和对应的自动发货配置。
    当京东推送订单时，系统根据 shop_id + sku_id 匹配商品，
    若配置了91卡券则自动提卡发货。
    """
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # 所属店铺
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'),
                        nullable=False, comment='所属店铺ID')

    # 商品基本信息
    product_name = db.Column(db.String(200), nullable=False, comment='商品名称')
    jd_product_id = db.Column(db.String(100), comment='京东商品ID（用于抓取SKU信息）')
    sku_id = db.Column(db.String(100), comment='京东SKU ID（精确匹配订单SKU）')
    sku_name = db.Column(db.String(200), comment='SKU名称/套餐名称')

    # 发货方式：0=手动 1=91卡券卡密 2=直充（预留）
    deliver_type = db.Column(db.SmallInteger, default=0,
                              comment='发货方式：0=手动 1=91卡券卡密 2=直充API预留')

    # 91卡券配置（发货方式=1时有效）
    card91_card_type_id = db.Column(db.String(100), comment='91卡券卡种ID')
    card91_card_type_name = db.Column(db.String(200), comment='91卡券卡种名称')
    card91_plan_id = db.Column(db.String(100), comment='91卡券方案ID（可选）')

    # 直充API预留（发货方式=2时使用，后续扩展）
    direct_charge_api_type = db.Column(db.String(50), comment='直充API类型（预留）')
    direct_charge_api_config = db.Column(db.Text, comment='直充API配置JSON（预留）')

    # 商品状态
    is_enabled = db.Column(db.SmallInteger, default=1, comment='是否启用：0=禁用 1=启用')
    remark = db.Column(db.String(500), comment='备注')

    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now,
                             comment='更新时间')

    # 关联关系
    shop = db.relationship('Shop', backref=db.backref('products', lazy='dynamic'))

    # 唯一索引：同一店铺下同一SKU只能有一个配置
    __table_args__ = (
        db.Index('idx_shop_sku', 'shop_id', 'sku_id'),
    )

    # 发货方式标签映射
    DELIVER_TYPE_MAP = {
        0: '手动发货',
        1: '91卡券卡密',
        2: '直充API（预留）',
    }

    @property
    def deliver_type_label(self):
        """发货方式中文标签"""
        return self.DELIVER_TYPE_MAP.get(self.deliver_type, '未知')

    @property
    def status_label(self):
        """状态标签"""
        return '启用' if self.is_enabled == 1 else '禁用'

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'shop_id': self.shop_id,
            'shop_name': self.shop.shop_name if self.shop else '',
            'product_name': self.product_name,
            'jd_product_id': self.jd_product_id or '',
            'sku_id': self.sku_id or '',
            'sku_name': self.sku_name or '',
            'deliver_type': self.deliver_type,
            'deliver_type_label': self.deliver_type_label,
            'card91_card_type_id': self.card91_card_type_id or '',
            'card91_card_type_name': self.card91_card_type_name or '',
            'card91_plan_id': self.card91_plan_id or '',
            'is_enabled': self.is_enabled,
            'remark': self.remark or '',
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }
