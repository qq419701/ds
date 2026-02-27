from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request
from config import Config, TestConfig
from app.extensions import db, login_manager


def create_app(config_class=None):
    app = Flask(__name__)

    if config_class is None:
        app.config.from_object(Config)
    else:
        app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.shop import shop_bp
    from app.routes.order import order_bp
    from app.routes.user import user_bp
    from app.routes.notification import notification_bp
    from app.routes.statistics import statistics_bp
    from app.routes.api import api_bp
    from app.routes.jd_game_api import jd_game_api_bp
    from app.routes.jd_general_api import jd_general_api_bp
    from app.routes.operation_log import operation_log_bp
    from app.routes.api_log import api_log_bp
    from app.routes.agiso_push import agiso_push_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(shop_bp, url_prefix='/shop')
    app.register_blueprint(order_bp, url_prefix='/order')
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(notification_bp, url_prefix='/notification')
    app.register_blueprint(statistics_bp, url_prefix='/statistics')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(jd_game_api_bp, url_prefix='/api/game')
    app.register_blueprint(jd_general_api_bp, url_prefix='/api/general')
    app.register_blueprint(operation_log_bp, url_prefix='/operation-log')
    app.register_blueprint(api_log_bp, url_prefix='/api-log')
    app.register_blueprint(agiso_push_bp, url_prefix='/api/agiso')

    # API日志中间件 - 记录所有 /api/ 请求
    @app.after_request
    def log_api_request(response):
        if request.path.startswith('/api/') and 'new-order-count' not in request.path:
            try:
                from app.models.api_log import ApiLog
                from app.models.shop import Shop

                # 判断接口类型
                if '/api/game/direct' in request.path:
                    api_type = '游戏直充接单'
                elif '/api/game/query' in request.path:
                    api_type = '游戏直充查询'
                elif '/api/game/card-query' in request.path:
                    api_type = '游戏卡密查询'
                elif '/api/game/card' in request.path:
                    api_type = '游戏卡密接单'
                elif '/api/general/distill' in request.path:
                    api_type = '通用交易接单'
                elif '/api/general/query' in request.path:
                    api_type = '通用交易查询'
                else:
                    api_type = '其他API'

                req_body = request.get_data(as_text=True)[:5000]

                resp_body = ''
                try:
                    resp_body = response.get_data(as_text=True)[:5000]
                except Exception:
                    pass

                shop_id = None
                form_data = request.form.to_dict()
                customer_id = form_data.get('customerId', '')
                if customer_id:
                    shop = Shop.query.filter_by(game_customer_id=str(customer_id), is_enabled=1).first()
                    if shop:
                        shop_id = shop.id

                log = ApiLog(
                    shop_id=shop_id,
                    api_type=api_type,
                    request_method=request.method,
                    request_url=request.url[:500],
                    request_headers=str(dict(list(request.headers)[:10]))[:2000],
                    request_body=req_body,
                    response_status=response.status_code,
                    response_body=resp_body,
                    ip_address=request.remote_addr or request.headers.get('X-Forwarded-For', ''),
                )
                db.session.add(log)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                import logging
                logging.getLogger(__name__).error(f"API日志记录失败: {e}")
        return response

    return app
