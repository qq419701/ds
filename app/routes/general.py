import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.extensions import db
from app.models.shop import Shop
from app.models.order import Order
from app.utils.sign import verify_general_sign, general_sign
from app.utils.ip_whitelist import check_ip

general_bp = Blueprint('general', __name__)
logger = logging.getLogger(__name__)


def get_shop_by_vendor_id(vendor_id):
    """根据vendorId找到对应的店铺"""
    return Shop.query.filter_by(general_vendor_id=str(vendor_id)).first()


@general_bp.route('/api/general/distill', methods=['POST'])
def general_distill():
    """通用交易接单"""
    # 1. 获取表单参数
    form_data = request.form.to_dict()

    vendor_id = str(form_data.get('vendorId', ''))
    jd_order_no = str(form_data.get('jdOrderNo', ''))

    # 2. 验证IP白名单
    if not check_ip(request):
        logger.warning(f"IP拦截 remote_addr={request.remote_addr}")
        return jsonify({"code": "JDO_500", "message": "IP不在白名单"}), 403

    # 3. 找到对应店铺
    shop = get_shop_by_vendor_id(vendor_id)
    if not shop:
        logger.warning(f"店铺不存在 vendorId={vendor_id}")
        return jsonify({"code": "JDO_500", "message": "商家编号不存在"})

    # 4. 验证签名
    if not current_app.config.get('SKIP_SIGN_VERIFY', False):
        if not verify_general_sign(form_data, shop.general_md5_secret):
            logger.warning(f"签名验证失败 vendorId={vendor_id}")
            return jsonify({"code": "JDO_500", "message": "签名错误"})

    # 5. 处理订单
    from app.services.general_service import process_general_order, auto_deliver_general
    order, is_new = process_general_order(shop, form_data)

    if not is_new:
        # 返回已有订单信息
        logger.info(f"重复订单 jd_order_no={jd_order_no}")

    # 6. 如果启用阿奇索，调用阿奇索发货
    if is_new and shop.agiso_enabled == 1:
        from app.services.agiso_service import send_general
        send_general(shop, order)
    elif is_new and shop.auto_deliver == 1:
        auto_deliver_general(shop, order)

    # 7. 构建响应
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    resp_params = {
        "jdOrderNo": int(order.jd_order_no) if order.jd_order_no and order.jd_order_no.isdigit() else order.jd_order_no,
        "agentOrderNo": order.agent_order_no,
        "produceStatus": 3,
        "code": "JDO_201",
        "signType": "MD5",
        "timestamp": timestamp
    }

    # 对响应签名
    sign_params = {
        "jdOrderNo": str(resp_params["jdOrderNo"]),
        "agentOrderNo": resp_params["agentOrderNo"],
        "produceStatus": str(resp_params["produceStatus"]),
        "code": resp_params["code"],
        "timestamp": timestamp
    }
    resp_params["sign"] = general_sign(sign_params, shop.general_md5_secret)

    return jsonify(resp_params)


@general_bp.route('/api/general/query', methods=['POST'])
def general_query():
    """通用交易反查订单"""
    form_data = request.form.to_dict()

    vendor_id = str(form_data.get('vendorId', ''))
    jd_order_no = str(form_data.get('jdOrderNo', ''))

    if not check_ip(request):
        return jsonify({"code": "JDO_500", "message": "IP不在白名单"}), 403

    shop = get_shop_by_vendor_id(vendor_id)
    if not shop:
        return jsonify({"code": "JDO_500", "message": "商家编号不存在"})

    if not current_app.config.get('SKIP_SIGN_VERIFY', False):
        if not verify_general_sign(form_data, shop.general_md5_secret):
            return jsonify({"code": "JDO_500", "message": "签名错误"})

    order = Order.query.filter_by(jd_order_no=jd_order_no).first()
    if not order:
        return jsonify({"code": "JDO_500", "message": "订单不存在"})

    # produceStatus: 1=成功 2=失败 3=处理中 4=异常
    status_map = {0: 3, 1: 3, 2: 1, 3: 4, 4: 2}
    produce_status = status_map.get(order.order_status, 3)

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    resp_params = {
        "jdOrderNo": int(jd_order_no) if jd_order_no.isdigit() else jd_order_no,
        "agentOrderNo": order.agent_order_no,
        "produceStatus": produce_status,
        "code": "JDO_201",
        "signType": "MD5",
        "timestamp": timestamp
    }

    sign_params = {
        "jdOrderNo": str(resp_params["jdOrderNo"]),
        "agentOrderNo": resp_params["agentOrderNo"],
        "produceStatus": str(resp_params["produceStatus"]),
        "code": resp_params["code"],
        "timestamp": timestamp
    }
    resp_params["sign"] = general_sign(sign_params, shop.general_md5_secret)

    return jsonify(resp_params)
