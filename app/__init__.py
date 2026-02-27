from flask import Flask
from config import config
from app.extensions import db, migrate, login_manager
import os


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    login_manager.login_view = 'admin.login'

    # 注册蓝图
    from app.routes.game import game_bp
    from app.routes.general import general_bp
    from app.routes.agiso import agiso_bp
    from app.routes.admin import admin_bp
    from app.routes.settings import settings_bp

    app.register_blueprint(game_bp)
    app.register_blueprint(general_bp)
    app.register_blueprint(agiso_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(settings_bp)

    return app
