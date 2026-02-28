"""初始化数据库并创建默认管理员用户。

包含所有数据表的创建，以及新增字段的迁移处理。
"""
from app import create_app
from app.extensions import db
from app.models.user import User


def init_db():
    app = create_app()
    with app.app_context():
        # 导入所有模型以确保 db.create_all() 能识别
        from app.models.shop import Shop
        from app.models.order import Order
        from app.models.product import Product
        from app.models.order_event import OrderEvent
        from app.models.notification_log import NotificationLog
        from app.models.api_log import ApiLog
        from app.models.operation_log import OperationLog

        # 创建所有不存在的表（新表会自动创建，已有表不变）
        db.create_all()

        # 对已有 shops 表进行字段迁移（添加91卡券字段）
        _migrate_shop_table(db)

        # 创建默认管理员账号
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                name='超级管理员',
                role='admin',
                can_view_order=1,
                can_deliver=1,
                can_refund=1,
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print('默认管理员已创建：admin / admin123')
        else:
            print('管理员账号已存在')

        print('数据库初始化完成')


def _migrate_shop_table(db):
    """为 shops 表添加91卡券相关字段（若字段不存在则添加）。"""
    try:
        engine = db.engine
        # 检查并添加新字段
        new_columns = [
            ('card91_api_url', 'VARCHAR(500) COMMENT "91卡券API地址"'),
            ('card91_api_key', 'VARCHAR(200) COMMENT "91卡券API密钥"'),
            ('card91_api_secret', 'VARCHAR(500) COMMENT "91卡券API签名密钥"'),
        ]
        with engine.connect() as conn:
            # 获取现有列名
            try:
                result = conn.execute(db.text('DESCRIBE shops'))
                existing_columns = {row[0] for row in result}
            except Exception:
                # SQLite 不支持 DESCRIBE，使用 PRAGMA
                try:
                    result = conn.execute(db.text('PRAGMA table_info(shops)'))
                    existing_columns = {row[1] for row in result}
                except Exception:
                    return

            # 逐个添加缺失字段（字段名和类型均来自本地白名单，无注入风险）
            ALLOWED_COLUMNS = {
                'card91_api_url', 'card91_api_key', 'card91_api_secret'
            }
            for col_name, col_def in new_columns:
                if col_name not in ALLOWED_COLUMNS:
                    continue  # 安全白名单校验
                if col_name not in existing_columns:
                    try:
                        conn.execute(db.text(f'ALTER TABLE shops ADD COLUMN {col_name} {col_def}'))
                        conn.commit()
                        print(f'已添加字段：shops.{col_name}')
                    except Exception as e:
                        print(f'添加字段 {col_name} 失败（可能已存在）：{e}')
    except Exception as e:
        print(f'数据库迁移失败（不影响使用）：{e}')


if __name__ == '__main__':
    init_db()
