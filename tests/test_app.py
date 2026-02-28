import json
import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User, UserShopPermission
from app.models.shop import Shop
from app.models.order import Order
from app.models.notification_log import NotificationLog
from config import TestConfig


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_user(db):
    user = User(username='admin', name='Admin', role='admin',
                can_view_order=1, can_deliver=1, can_refund=1)
    user.set_password('admin123')
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def operator_user(db):
    user = User(username='operator', name='Operator', role='operator',
                can_view_order=1, can_deliver=1, can_refund=0)
    user.set_password('op123')
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def shop(db):
    s = Shop(shop_name='测试店铺', shop_code='TEST001', shop_type=1,
             is_enabled=1, notify_enabled=0)
    db.session.add(s)
    db.session.commit()
    return s


@pytest.fixture
def shop_with_notify(db):
    s = Shop(shop_name='通知店铺', shop_code='NOTIFY001', shop_type=1,
             is_enabled=1, notify_enabled=1,
             dingtalk_webhook='https://oapi.dingtalk.com/robot/send?access_token=test',
             dingtalk_secret='test_secret')
    db.session.add(s)
    db.session.commit()
    return s


@pytest.fixture
def order(db, shop):
    o = Order(order_no='ORD001', jd_order_no='JD001', shop_id=shop.id,
              shop_type=1, order_type=1, amount=10000, quantity=1,
              product_info='测试商品', produce_account='13800138000')
    db.session.add(o)
    db.session.commit()
    return o


@pytest.fixture
def card_order(db, shop):
    o = Order(order_no='ORD002', jd_order_no='JD002', shop_id=shop.id,
              shop_type=1, order_type=2, amount=20000, quantity=2,
              product_info='卡密商品')
    db.session.add(o)
    db.session.commit()
    return o


def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=True)


# ---- Model Tests ----

class TestUserModel:
    def test_password_hashing(self, app, db):
        user = User(username='test', role='operator')
        user.set_password('mypassword')
        assert user.check_password('mypassword')
        assert not user.check_password('wrongpassword')

    def test_is_admin(self, app, admin_user):
        assert admin_user.is_admin is True

    def test_is_not_admin(self, app, operator_user):
        assert operator_user.is_admin is False

    def test_is_active(self, app, admin_user):
        assert admin_user.is_active is True

    def test_get_permitted_shop_ids_admin(self, app, admin_user):
        assert admin_user.get_permitted_shop_ids() is None

    def test_get_permitted_shop_ids_operator(self, app, db, operator_user, shop):
        perm = UserShopPermission(user_id=operator_user.id, shop_id=shop.id)
        db.session.add(perm)
        db.session.commit()
        ids = operator_user.get_permitted_shop_ids()
        assert shop.id in ids

    def test_has_shop_permission_admin(self, app, admin_user):
        assert admin_user.has_shop_permission(999) is True

    def test_has_shop_permission_operator(self, app, db, operator_user, shop):
        assert operator_user.has_shop_permission(shop.id) is False
        perm = UserShopPermission(user_id=operator_user.id, shop_id=shop.id)
        db.session.add(perm)
        db.session.commit()
        assert operator_user.has_shop_permission(shop.id) is True


class TestShopModel:
    def test_shop_type_label(self, app, shop):
        assert shop.shop_type_label == '游戏点卡'
        shop.shop_type = 2
        assert shop.shop_type_label == '通用交易'

    def test_to_dict(self, app, shop):
        d = shop.to_dict()
        assert d['shop_name'] == '测试店铺'
        assert d['shop_code'] == 'TEST001'


class TestOrderModel:
    def test_order_status_label(self, app, order):
        assert order.order_status_label == '待支付'
        order.order_status = 2
        assert order.order_status_label == '已完成'

    def test_amount_yuan(self, app, order):
        assert order.amount_yuan == '100.00'

    def test_card_info_parsed(self, app, card_order):
        assert card_order.card_info_parsed == []
        card_order.card_info = json.dumps([{'cardNo': '111', 'cardPwd': 'aaa'}])
        assert len(card_order.card_info_parsed) == 1

    def test_to_dict(self, app, order):
        d = order.to_dict()
        assert d['order_no'] == 'ORD001'
        assert d['amount'] == 10000


# ---- Auth Tests ----

class TestAuth:
    def test_login_page(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200

    def test_login_success(self, client, admin_user):
        resp = client.post('/login', data={'username': 'admin', 'password': 'admin123'},
                           follow_redirects=True)
        assert resp.status_code == 200

    def test_login_fail(self, client, admin_user):
        resp = client.post('/login', data={'username': 'admin', 'password': 'wrong'},
                           follow_redirects=True)
        assert resp.status_code == 200
        assert '用户名或密码错误'.encode() in resp.data

    def test_logout(self, client, admin_user):
        login(client, 'admin', 'admin123')
        resp = client.get('/logout', follow_redirects=True)
        assert resp.status_code == 200

    def test_redirect_unauthenticated(self, client):
        resp = client.get('/order/')
        assert resp.status_code == 302


# ---- Order Route Tests ----

class TestOrderRoutes:
    def test_order_list(self, client, admin_user, order):
        login(client, 'admin', 'admin123')
        resp = client.get('/order/')
        assert resp.status_code == 200
        assert b'JD001' in resp.data

    def test_order_detail(self, client, admin_user, order):
        login(client, 'admin', 'admin123')
        resp = client.get(f'/order/detail/{order.id}')
        assert resp.status_code == 200

    def test_notify_success(self, client, admin_user, order):
        login(client, 'admin', 'admin123')
        resp = client.post(f'/order/notify-success/{order.id}',
                           content_type='application/json', data='{}')
        data = json.loads(resp.data)
        assert data['success'] is False  # No callback URL configured
        assert order.order_status != 2  # Status should not be updated

    def test_notify_refund(self, client, admin_user, order):
        login(client, 'admin', 'admin123')
        resp = client.post(f'/order/notify-refund/{order.id}',
                           content_type='application/json', data='{}')
        data = json.loads(resp.data)
        assert data['success'] is False  # No callback URL configured
        assert order.order_status != 4  # Status should not be updated to 已退款

    def test_deliver_card(self, client, admin_user, card_order):
        login(client, 'admin', 'admin123')
        cards = [{'cardNo': '111', 'cardPwd': 'aaa'}, {'cardNo': '222', 'cardPwd': 'bbb'}]
        resp = client.post(f'/order/deliver-card/{card_order.id}',
                           content_type='application/json',
                           data=json.dumps({'cards': cards}))
        data = json.loads(resp.data)
        assert data['success'] is False  # No callback URL configured
        assert card_order.order_status != 2  # Status should not be updated

    def test_deliver_card_wrong_count(self, client, admin_user, card_order):
        login(client, 'admin', 'admin123')
        cards = [{'cardNo': '111', 'cardPwd': 'aaa'}]
        resp = client.post(f'/order/deliver-card/{card_order.id}',
                           content_type='application/json',
                           data=json.dumps({'cards': cards}))
        data = json.loads(resp.data)
        assert data['success'] is False

    def test_self_debug(self, client, admin_user, order):
        login(client, 'admin', 'admin123')
        resp = client.post(f'/order/self-debug/{order.id}',
                           content_type='application/json',
                           data=json.dumps({'status': 'success'}))
        data = json.loads(resp.data)
        assert data['success'] is True
        assert order.order_status == 2

    def test_self_debug_processing(self, client, admin_user, order):
        login(client, 'admin', 'admin123')
        resp = client.post(f'/order/self-debug/{order.id}',
                           content_type='application/json',
                           data=json.dumps({'status': 'processing'}))
        data = json.loads(resp.data)
        assert data['success'] is True
        assert order.order_status == 1

    def test_self_debug_failed(self, client, admin_user, order):
        login(client, 'admin', 'admin123')
        resp = client.post(f'/order/self-debug/{order.id}',
                           content_type='application/json',
                           data=json.dumps({'status': 'failed'}))
        data = json.loads(resp.data)
        assert data['success'] is True
        assert order.order_status == 3

    def test_order_filter_by_shop(self, client, admin_user, order, shop):
        login(client, 'admin', 'admin123')
        resp = client.get(f'/order/?shop_id={shop.id}')
        assert resp.status_code == 200
        assert b'JD001' in resp.data

    def test_operator_no_permission(self, client, db, operator_user, order):
        login(client, 'operator', 'op123')
        resp = client.post(f'/order/notify-refund/{order.id}',
                           content_type='application/json', data='{}')
        data = json.loads(resp.data)
        assert data['success'] is False


# ---- Shop Route Tests ----

class TestShopRoutes:
    def test_shop_list_admin(self, client, admin_user, shop):
        login(client, 'admin', 'admin123')
        resp = client.get('/shop/')
        assert resp.status_code == 200

    def test_shop_list_operator_forbidden(self, client, operator_user):
        login(client, 'operator', 'op123')
        resp = client.get('/shop/', follow_redirects=True)
        assert resp.status_code == 200  # redirected

    def test_shop_create(self, client, admin_user):
        login(client, 'admin', 'admin123')
        resp = client.post('/shop/create', data={
            'shop_name': '新店铺',
            'shop_code': 'NEW001',
            'shop_type': '1',
            'is_enabled': '1',
            'notify_enabled': '0',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert Shop.query.filter_by(shop_code='NEW001').first() is not None

    def test_shop_edit(self, client, admin_user, shop):
        login(client, 'admin', 'admin123')
        resp = client.post(f'/shop/edit/{shop.id}', data={
            'shop_name': '修改后店铺',
            'shop_type': '2',
            'is_enabled': '1',
            'notify_enabled': '1',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert shop.shop_name == '修改后店铺'

    def test_shop_delete(self, client, admin_user, shop):
        login(client, 'admin', 'admin123')
        resp = client.post(f'/shop/delete/{shop.id}', follow_redirects=True)
        assert resp.status_code == 200
        assert Shop.query.get(shop.id) is None


# ---- User Route Tests ----

class TestUserRoutes:
    def test_user_list(self, client, admin_user):
        login(client, 'admin', 'admin123')
        resp = client.get('/user/')
        assert resp.status_code == 200

    def test_user_create(self, client, admin_user):
        login(client, 'admin', 'admin123')
        resp = client.post('/user/create', data={
            'username': 'newuser',
            'password': 'newpass123',
            'name': 'New User',
            'role': 'operator',
            'can_view_order': '1',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert User.query.filter_by(username='newuser').first() is not None


# ---- API Tests ----

class TestAPI:
    def test_create_order_api(self, client, shop):
        resp = client.post('/api/order/create',
                           content_type='application/json',
                           data=json.dumps({
                               'shop_code': 'TEST001',
                               'jd_order_no': 'JD_API_001',
                               'order_type': 1,
                               'amount': 5000,
                               'quantity': 1,
                               'product_info': 'API测试商品',
                               'produce_account': '13900139000',
                           }))
        data = json.loads(resp.data)
        assert data['success'] is True
        assert 'order_no' in data

    def test_create_order_invalid_shop(self, client):
        resp = client.post('/api/order/create',
                           content_type='application/json',
                           data=json.dumps({
                               'shop_code': 'INVALID',
                               'jd_order_no': 'JD_FAIL',
                               'amount': 1000,
                           }))
        data = json.loads(resp.data)
        assert data['success'] is False


# ---- Notification Service Tests ----

class TestNotificationService:
    def test_build_order_message(self, app, order, shop):
        from app.services.notification import build_order_message
        msg = build_order_message(order, shop)
        assert '新订单通知' in msg
        assert 'JD001' in msg
        assert '测试店铺' in msg

    def test_send_order_notification_disabled(self, app, db, order, shop):
        from app.services.notification import send_order_notification
        # shop.notify_enabled == 0, should not send
        send_order_notification(order, shop)
        assert NotificationLog.query.count() == 0


# ---- 京东游戏点卡平台接口测试 ----

class TestJdGameService:
    def test_generate_game_sign(self, app):
        """测试京东游戏点卡平台MD5签名生成"""
        from app.services.jd_game import generate_game_sign
        params = {'jdOrderId': 'JD001', 'orderId': 'ORD001', 'status': 'SUCCESS'}
        sign = generate_game_sign(params, 'test_secret')
        assert sign is not None
        assert len(sign) == 32  # MD5签名为32位

    def test_verify_game_sign_valid(self, app):
        """测试京东游戏点卡平台签名验证 - 有效签名"""
        from app.services.jd_game import generate_game_sign, verify_game_sign
        params = {'jdOrderId': 'JD001', 'orderId': 'ORD001', 'status': 'SUCCESS'}
        sign = generate_game_sign(params, 'test_secret')
        params['sign'] = sign
        assert verify_game_sign(params, 'test_secret') is True

    def test_verify_game_sign_invalid(self, app):
        """测试京东游戏点卡平台签名验证 - 无效签名"""
        from app.services.jd_game import verify_game_sign
        params = {'jdOrderId': 'JD001', 'orderId': 'ORD001', 'sign': 'invalid_sign'}
        assert verify_game_sign(params, 'test_secret') is False

    def test_verify_game_sign_no_secret(self, app):
        """测试京东游戏点卡平台签名验证 - 未配置密钥时跳过验签"""
        from app.services.jd_game import verify_game_sign
        params = {'jdOrderId': 'JD001'}
        assert verify_game_sign(params, '') is True
        assert verify_game_sign(params, None) is True

    def test_verify_game_sign_missing_sign(self, app):
        """测试京东游戏点卡平台签名验证 - 缺少sign参数"""
        from app.services.jd_game import verify_game_sign
        params = {'jdOrderId': 'JD001', 'orderId': 'ORD001'}
        assert verify_game_sign(params, 'test_secret') is False

    def test_sign_consistency(self, app):
        """测试签名一致性 - 相同参数应产生相同签名"""
        from app.services.jd_game import generate_game_sign
        params = {'b': '2', 'a': '1', 'c': '3'}
        sign1 = generate_game_sign(params, 'secret')
        sign2 = generate_game_sign(params, 'secret')
        assert sign1 == sign2

    def test_sign_order_independent(self, app):
        """测试签名与参数顺序无关"""
        from app.services.jd_game import generate_game_sign
        params1 = {'a': '1', 'b': '2', 'c': '3'}
        params2 = {'c': '3', 'a': '1', 'b': '2'}
        assert generate_game_sign(params1, 'secret') == generate_game_sign(params2, 'secret')


# ---- 京东通用交易平台接口测试 ----

class TestJdGeneralService:
    def test_generate_general_sign(self, app):
        """测试京东通用交易平台MD5签名生成"""
        from app.services.jd_general import generate_general_sign
        params = {'venderId': 'V001', 'jdOrderId': 'JD001', 'status': 'SUCCESS'}
        sign = generate_general_sign(params, 'test_secret')
        assert sign is not None
        assert len(sign) == 32

    def test_verify_general_sign_valid(self, app):
        """测试京东通用交易平台签名验证 - 有效签名"""
        from app.services.jd_general import generate_general_sign, verify_general_sign
        params = {'venderId': 'V001', 'jdOrderId': 'JD001', 'status': 'SUCCESS'}
        sign = generate_general_sign(params, 'test_secret')
        params['sign'] = sign
        assert verify_general_sign(params, 'test_secret') is True

    def test_verify_general_sign_invalid(self, app):
        """测试京东通用交易平台签名验证 - 无效签名"""
        from app.services.jd_general import verify_general_sign
        params = {'venderId': 'V001', 'sign': 'bad_sign'}
        assert verify_general_sign(params, 'test_secret') is False

    def test_verify_general_sign_no_secret(self, app):
        """测试京东通用交易平台签名验证 - 未配置密钥时跳过验签"""
        from app.services.jd_general import verify_general_sign
        params = {'venderId': 'V001'}
        assert verify_general_sign(params, '') is True
        assert verify_general_sign(params, None) is True


# ---- 阿奇索开放平台接口测试 ----

class TestAgisoService:
    def test_generate_agiso_sign(self, app):
        """测试阿奇索开放平台签名生成"""
        from app.services.agiso import generate_agiso_sign
        params = {'appId': 'APP001', 'jdOrderId': 'JD001'}
        sign = generate_agiso_sign(params, 'app_secret')
        assert sign is not None
        assert len(sign) == 32

    def test_agiso_sign_order_independent(self, app):
        """测试阿奇索签名与参数顺序无关"""
        from app.services.agiso import generate_agiso_sign
        params1 = {'appId': 'APP001', 'jdOrderId': 'JD001', 'orderId': 'ORD001'}
        params2 = {'orderId': 'ORD001', 'appId': 'APP001', 'jdOrderId': 'JD001'}
        assert generate_agiso_sign(params1, 'secret') == generate_agiso_sign(params2, 'secret')

    def test_agiso_deliver_not_enabled(self, app, db, shop, order):
        """测试阿奇索未启用时返回错误"""
        from app.services.agiso import agiso_auto_deliver
        shop.agiso_enabled = 0
        ok, msg, data = agiso_auto_deliver(shop, order)
        assert ok is False
        assert '未启用' in msg

    def test_agiso_deliver_missing_config(self, app, db, shop, order):
        """测试阿奇索配置不完整时返回错误"""
        from app.services.agiso import agiso_auto_deliver
        shop.agiso_enabled = 1
        shop.agiso_app_id = None
        ok, msg, data = agiso_auto_deliver(shop, order)
        assert ok is False
        assert '配置不完整' in msg

    def test_agiso_deliver_missing_token(self, app, db, shop, order):
        """测试阿奇索未配置访问令牌时返回错误"""
        from app.services.agiso import agiso_auto_deliver
        shop.agiso_enabled = 1
        shop.agiso_app_id = 'APP001'
        shop.agiso_app_secret = 'SECRET'
        shop.agiso_access_token = None
        ok, msg, data = agiso_auto_deliver(shop, order)
        assert ok is False
        assert '访问令牌' in msg


# ---- API签名验证集成测试 ----

class TestAPISignatureVerification:
    def test_create_order_with_valid_game_sign(self, client, db):
        """测试京东游戏点卡平台订单创建 - 有效签名"""
        from app.services.jd_game import generate_game_sign
        shop = Shop(shop_name='签名测试店', shop_code='SIGN001', shop_type=1,
                    is_enabled=1, game_md5_secret='test_key_123')
        db.session.add(shop)
        db.session.commit()

        params = {
            'shop_code': 'SIGN001',
            'jd_order_no': 'JD_SIGN_001',
            'order_type': 1,
            'amount': 5000,
            'quantity': 1,
            'product_info': '签名测试商品',
        }
        params['sign'] = generate_game_sign(
            {k: str(v) for k, v in params.items()}, 'test_key_123'
        )

        resp = client.post('/api/order/create',
                           content_type='application/json',
                           data=json.dumps(params))
        data = json.loads(resp.data)
        assert data['success'] is True

    def test_create_order_with_invalid_game_sign(self, client, db):
        """测试京东游戏点卡平台订单创建 - 无效签名应被拒绝"""
        shop = Shop(shop_name='签名测试店', shop_code='SIGN002', shop_type=1,
                    is_enabled=1, game_md5_secret='test_key_123')
        db.session.add(shop)
        db.session.commit()

        params = {
            'shop_code': 'SIGN002',
            'jd_order_no': 'JD_SIGN_002',
            'amount': 5000,
            'sign': 'invalid_sign_value',
        }

        resp = client.post('/api/order/create',
                           content_type='application/json',
                           data=json.dumps(params))
        data = json.loads(resp.data)
        assert data['success'] is False
        assert '签名验证失败' in data['message']

    def test_create_order_without_sign_config(self, client, shop):
        """测试未配置签名密钥的店铺 - 不需要签名验证"""
        resp = client.post('/api/order/create',
                           content_type='application/json',
                           data=json.dumps({
                               'shop_code': 'TEST001',
                               'jd_order_no': 'JD_NOSIGN_001',
                               'amount': 3000,
                           }))
        data = json.loads(resp.data)
        assert data['success'] is True


# ---- 91卡券服务测试 ----

class TestCard91Service:
    def test_build_sign_consistency(self, app):
        """测试91卡券签名一致性"""
        from app.services.card91 import _build_sign
        params = {'api_key': 'test_key', 'timestamp': '1234567890', 'card_type_id': '123'}
        sign1 = _build_sign(params, 'test_secret')
        sign2 = _build_sign(params, 'test_secret')
        assert sign1 == sign2
        assert len(sign1) == 32  # MD5签名为32位

    def test_build_sign_order_independent(self, app):
        """测试91卡券签名与参数顺序无关"""
        from app.services.card91 import _build_sign
        params1 = {'a': '1', 'b': '2', 'c': '3'}
        params2 = {'c': '3', 'a': '1', 'b': '2'}
        assert _build_sign(params1, 'secret') == _build_sign(params2, 'secret')

    def test_build_sign_excludes_sign_param(self, app):
        """测试签名时排除sign参数本身"""
        from app.services.card91 import _build_sign
        params_without = {'api_key': 'key', 'timestamp': '123'}
        params_with = {'api_key': 'key', 'timestamp': '123', 'sign': 'old_sign'}
        assert _build_sign(params_without, 'secret') == _build_sign(params_with, 'secret')

    def test_no_api_key_returns_error(self, app, shop):
        """测试未配置API密钥时返回错误"""
        from app.services.card91 import card91_fetch_cards
        shop.card91_api_key = None
        ok, msg, cards = card91_fetch_cards(shop, 'type_1', 1, 'ORD001')
        assert ok is False
        assert '未配置' in msg
        assert cards == []

    def test_auto_deliver_no_product_config(self, app, shop, order):
        """测试商品未配置91卡券时返回错误"""
        from app.services.card91 import card91_auto_deliver
        ok, msg, cards = card91_auto_deliver(shop, order, None)
        assert ok is False
        assert '未配置' in msg or '卡种' in msg

    def test_test_connection_no_key(self, app, shop):
        """测试连接时未配置密钥返回错误"""
        from app.services.card91 import card91_test_connection
        shop.card91_api_key = None
        ok, msg = card91_test_connection(shop)
        assert ok is False


# ---- 商品管理路由测试 ----

class TestProductRoutes:
    def test_product_list_admin(self, client, admin_user):
        """管理员可以访问商品列表"""
        login(client, 'admin', 'admin123')
        resp = client.get('/product/')
        assert resp.status_code == 200

    def test_product_list_operator(self, client, operator_user):
        """操作员可以访问商品列表（只看授权店铺）"""
        login(client, 'operator', 'op123')
        resp = client.get('/product/')
        assert resp.status_code == 200

    def test_product_create(self, client, admin_user, shop):
        """管理员可以创建商品配置"""
        from app.models.product import Product
        login(client, 'admin', 'admin123')
        resp = client.post('/product/create', data={
            'shop_id': str(shop.id),
            'product_name': '爱奇艺月卡',
            'sku_id': 'SKU001',
            'deliver_type': '1',
            'card91_card_type_id': 'TYPE001',
            'card91_card_type_name': '爱奇艺卡',
            'is_enabled': '1',
        }, follow_redirects=True)
        assert resp.status_code == 200
        p = Product.query.filter_by(sku_id='SKU001').first()
        assert p is not None
        assert p.deliver_type == 1

    def test_product_edit(self, client, admin_user, db, shop):
        """管理员可以编辑商品配置"""
        from app.models.product import Product
        product = Product(shop_id=shop.id, product_name='测试商品', deliver_type=0, is_enabled=1)
        db.session.add(product)
        db.session.commit()

        login(client, 'admin', 'admin123')
        resp = client.post(f'/product/edit/{product.id}', data={
            'shop_id': str(shop.id),
            'product_name': '修改后商品',
            'deliver_type': '0',
            'is_enabled': '1',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert product.product_name == '修改后商品'

    def test_product_delete(self, client, admin_user, db, shop):
        """管理员可以删除商品配置"""
        from app.models.product import Product
        product = Product(shop_id=shop.id, product_name='待删除商品', deliver_type=0, is_enabled=1)
        db.session.add(product)
        db.session.commit()
        pid = product.id

        login(client, 'admin', 'admin123')
        resp = client.post(f'/product/delete/{pid}', follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(Product, pid) is None

    def test_card91_types_api_no_key(self, client, admin_user, shop):
        """未配置91卡券密钥时获取卡种列表返回错误"""
        login(client, 'admin', 'admin123')
        resp = client.get(f'/product/api/card91-types/{shop.id}')
        data = json.loads(resp.data)
        assert data['success'] is False
        assert '密钥' in data['message']


# ---- 订单事件日志测试 ----

class TestOrderEvent:
    def test_order_event_model(self, app, db, order):
        """测试订单事件模型"""
        from app.models.order_event import OrderEvent
        event = OrderEvent(
            order_id=order.id,
            order_no=order.order_no,
            event_type='order_created',
            event_desc='订单创建测试',
            result='info',
        )
        db.session.add(event)
        db.session.commit()

        assert event.id is not None
        assert event.event_type_label == '📦 订单创建'
        d = event.to_dict()
        assert d['event_type'] == 'order_created'
        assert d['result'] == 'info'

    def test_order_detail_html_with_events(self, client, admin_user, db, order):
        """订单详情弹窗HTML包含事件日志"""
        from app.models.order_event import OrderEvent
        event = OrderEvent(
            order_id=order.id,
            order_no=order.order_no,
            event_type='notify_success',
            event_desc='通知京东成功',
            result='success',
        )
        db.session.add(event)
        db.session.commit()

        login(client, 'admin', 'admin123')
        resp = client.get(f'/order/{order.id}/detail-html')
        assert resp.status_code == 200
        assert '通知京东成功'.encode() in resp.data

    def test_shop_model_card91_fields(self, app, db, shop):
        """店铺模型包含91卡券字段"""
        shop.card91_api_key = 'test_api_key'
        shop.card91_api_secret = 'test_secret'
        db.session.commit()
        assert shop.card91_api_key == 'test_api_key'
        d = shop.to_dict()
        # to_dict不暴露密钥
        assert 'auto_deliver' not in d

    def test_shop_form_no_auto_deliver(self, client, admin_user, shop):
        """编辑店铺时不再有auto_deliver字段"""
        login(client, 'admin', 'admin123')
        resp = client.get(f'/shop/edit/{shop.id}')
        assert resp.status_code == 200
        # 不应有发货方式选择器
        assert b'auto_deliver' not in resp.data
        # 不应有阿奇索配置
        assert '阿奇索'.encode() not in resp.data
        # 应有91卡券配置
        assert '91卡券'.encode() in resp.data
