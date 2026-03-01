"""91卡券（Agiso开放平台）接口服务。

API地址：https://gw-api.agiso.com
认证：Authorization: Bearer {agiso_access_token}，ApiVersion: 1
签名：md5(secret + key1value1key2value2... + secret) 按ASCII升序排列
"""
import hashlib
import json
import logging
import time
import requests

logger = logging.getLogger(__name__)

AGISO_BASE_URL = 'https://gw-api.agiso.com'
REQUEST_TIMEOUT = 30


def _build_sign(params, app_secret):
    """签名：secret前后包裹，参数按ASCII排序拼接后MD5。"""
    if not app_secret:
        return ''
    sorted_params = sorted(
        [(k, str(v)) for k, v in params.items() if k != 'sign' and v is not None],
        key=lambda x: x[0]
    )
    query_str = app_secret
    for k, v in sorted_params:
        query_str += f'{k}{v}'
    query_str += app_secret
    return hashlib.md5(query_str.encode('utf-8')).hexdigest().lower()


def _do_request(shop, endpoint, params=None):
    """发送 Agiso API POST 请求。"""
    if not shop or not shop.agiso_access_token:
        return False, '未配置91卡券AccessToken，请在店铺配置中填写', None

    url = f'{AGISO_BASE_URL}{endpoint}'

    req_params = {
        'timestamp': str(int(time.time())),
    }
    if params:
        req_params.update(params)

    if shop.agiso_app_secret:
        req_params['sign'] = _build_sign(req_params, shop.agiso_app_secret)

    headers = {
        'Authorization': f'Bearer {shop.agiso_access_token}',
        'ApiVersion': '1',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    try:
        resp = requests.post(url, data=req_params, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        result = resp.json()

        logger.debug(f'91卡券API [{endpoint}]: {json.dumps(result, ensure_ascii=False)[:500]}')

        is_success = result.get('IsSuccess', False)
        error_msg = result.get('Error_Msg', '')
        error_code = result.get('Error_Code', 0)
        data = result.get('Data', None)

        if is_success:
            return True, error_msg or '成功', data
        else:
            logger.warning(f'91卡券API错误 [{endpoint}]: code={error_code}, msg={error_msg}')
            return False, error_msg or f'接口错误码：{error_code}', data

    except requests.exceptions.ConnectionError as e:
        logger.error(f'91卡券API连接失败 [{endpoint}]: {e}')
        return False, '连接91卡券服务器失败，请检查网络', None
    except requests.exceptions.Timeout:
        logger.error(f'91卡券API超时 [{endpoint}]')
        return False, '请求91卡券服务器超时', None
    except Exception as e:
        logger.error(f'91卡券API异常 [{endpoint}]: {e}')
        return False, f'请求异常：{str(e)}', None


def card91_get_card_types(shop):
    """获取卡种列表。"""
    params = {'pageIndex': '1', 'pageSize': '100'}
    ok, msg, data = _do_request(shop, '/acpr/CardPwd/GetList', params)
    if ok and data:
        card_types = []
        items = []
        if isinstance(data, dict):
            items = data.get('List', data.get('list', []))
        elif isinstance(data, list):
            items = data
        for item in items:
            card_types.append({
                'id': str(item.get('IdNo', '')),
                'name': item.get('Title', ''),
                'stock': item.get('RemainingCount', 0),
                'total': item.get('TotalCount', 0),
                'used': item.get('UsedCount', 0),
            })
        return True, msg, card_types
    return ok, msg, []


def card91_fetch_cards(shop, card_type_id, quantity, order_no):
    """提卡。"""
    if not card_type_id:
        return False, '卡种ID未配置', []

    params = {
        'cpkId': str(card_type_id),
        'num': str(int(quantity)),
        'handPickOrderId': str(order_no),
    }
    ok, msg, data = _do_request(shop, '/acpr/CardPwd/HandPick', params)
    if ok and data:
        cards = []
        items = data.get('CardPwdArr', []) if isinstance(data, dict) else []
        for item in items:
            cards.append({
                'cardNo': str(item.get('c', '')),
                'cardPwd': str(item.get('p', '')),
                'expiry': str(item.get('d', '')),
            })
        if cards:
            return True, f'成功提取{len(cards)}张卡密', cards
        cpd_url = data.get('CpdUrl', '') if isinstance(data, dict) else ''
        if cpd_url:
            return True, '提卡成功', [{'cardNo': cpd_url, 'cardPwd': '', 'expiry': ''}]
        return False, '提卡成功但无卡密数据', []
    return ok, msg, []


def card91_get_stock(shop, card_type_id):
    """查询指定卡种库存。"""
    params = {'pageIndex': '1', 'pageSize': '100'}
    ok, msg, data = _do_request(shop, '/acpr/CardPwd/GetList', params)
    if ok and data:
        items = data.get('List', []) if isinstance(data, dict) else []
        for item in items:
            if str(item.get('IdNo', '')) == str(card_type_id):
                stock = item.get('RemainingCount', 0)
                return True, f'库存：{stock}张', stock
        return False, '未找到该卡种', 0
    return ok, msg, 0


def card91_test_connection(shop):
    """测试连接。"""
    ok, msg, data = _do_request(shop, '/acpr/CardPwd/GetList', {'pageIndex': '1', 'pageSize': '1'})
    if ok:
        total = 0
        if isinstance(data, dict):
            total = data.get('TotalCount', 0)
        return True, f'连接成功，共{total}个卡种'
    return False, msg


def card91_auto_deliver(shop, order, product):
    """自动提卡发货。"""
    if not product or not product.card91_card_type_id:
        return False, '商品未配置91卡券卡种ID', []

    if not shop or not shop.agiso_access_token:
        return False, '店铺未配置91卡券AccessToken', []

    logger.info(f'91卡券自动提卡：订单={order.order_no}，卡种={product.card91_card_type_id}，数量={order.quantity}')

    ok, msg, cards = card91_fetch_cards(
        shop, product.card91_card_type_id, order.quantity, order.order_no
    )

    if ok and len(cards) >= order.quantity:
        return True, f'成功提取{len(cards)}张卡密', cards[:order.quantity]
    elif ok:
        return False, f'卡密不足，需{order.quantity}张，只取到{len(cards)}张', []
    else:
        return False, f'提卡失败：{msg}', []
