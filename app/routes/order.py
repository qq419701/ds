import csv
import io
import json
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user

from app.extensions import db
from app.models.order import Order
from app.models.shop import Shop
from app.services.notification import send_order_notification
from app.services.jd_game import (
    callback_game_direct_success,
    callback_game_card_deliver,
    callback_game_refund,
)
from app.services.jd_general import (
    callback_general_success,
    callback_general_card_deliver,
    callback_general_refund,
)
import logging

# 注意：阿奇索（Agiso）相关功能已删除，系统统一使用91卡券接口自动发货。


logger = logging.getLogger(__name__)

order_bp = Blueprint('order', __name__)

# 回调状态常量：0=未回调 1=成功 2=失败
NOTIFY_STATUS_SUCCESS = 1
NOTIFY_STATUS_FAILED = 2


def _log_operation(user, action, target_type, target_id, detail):
    """记录操作日志辅助函数"""
    try:
        from app.models.operation_log import OperationLog
        log = OperationLog(
            user_id=user.id,
            username=user.username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=request.remote_addr,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.warning(f'记录操作日志失败: {e}')


@order_bp.route('/')
@login_required
def order_list():
    page = request.args.get('page', 1, type=int)
    per_page = 20

    query = Order.query

    # Permission filtering
    if not current_user.is_admin:
        permitted_ids = current_user.get_permitted_shop_ids()
        if permitted_ids is not None:
            query = query.filter(Order.shop_id.in_(permitted_ids)) if permitted_ids else query.filter(db.false())

    # Filters
    shop_id = request.args.get('shop_id', type=int)
    shop_type = request.args.get('shop_type', type=int)
    order_type = request.args.get('order_type', type=int)
    order_status = request.args.get('order_status', type=int)
    keyword = request.args.get('keyword', '').strip()
    jd_order_no = request.args.get('jd_order_no', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    if shop_id:
        query = query.filter(Order.shop_id == shop_id)
    if shop_type:
        query = query.filter(Order.shop_type == shop_type)
    if order_type:
        query = query.filter(Order.order_type == order_type)
    if order_status is not None and order_status != -1:
        query = query.filter(Order.order_status == order_status)
    
    # 关键字搜索：支持系统订单号、京东订单号、商品名称、充值账号
    if keyword:
        query = query.filter(
            db.or_(
                Order.order_no.like(f'%{keyword}%'),
                Order.jd_order_no.like(f'%{keyword}%'),
                Order.product_info.like(f'%{keyword}%'),
                Order.produce_account.like(f'%{keyword}%'),
            )
        )
    elif jd_order_no:
        query = query.filter(Order.jd_order_no.like(f'%{jd_order_no}%'))
    if start_date:
        try:
            query = query.filter(Order.create_time >= datetime.strptime(start_date, '%Y-%m-%d'))
        except ValueError:
            pass
    if end_date:
        try:
            query = query.filter(Order.create_time <= datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
        except ValueError:
            pass

    pagination = query.order_by(Order.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    orders = pagination.items

    # Get shops for filter dropdown
    if current_user.is_admin:
        shops = Shop.query.order_by(Shop.shop_name).all()
    else:
        permitted_ids = current_user.get_permitted_shop_ids()
        shops = Shop.query.filter(Shop.id.in_(permitted_ids)).order_by(Shop.shop_name).all() if permitted_ids else []

    return render_template('order/list.html', orders=orders, pagination=pagination, shops=shops)


@order_bp.route('/export')
@login_required
def export_orders():
    """导出订单为CSV"""
    query = Order.query

    # 权限过滤
    if not current_user.is_admin:
        permitted_ids = current_user.get_permitted_shop_ids()
        if permitted_ids is not None:
            query = query.filter(Order.shop_id.in_(permitted_ids)) if permitted_ids else query.filter(db.false())

    # 筛选条件（与list一致）
    shop_id = request.args.get('shop_id', type=int)
    shop_type = request.args.get('shop_type', type=int)
    order_type = request.args.get('order_type', type=int)
    order_status = request.args.get('order_status', type=int)
    keyword = request.args.get('keyword', '').strip()
    jd_order_no = request.args.get('jd_order_no', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    if shop_id:
        query = query.filter(Order.shop_id == shop_id)
    if shop_type:
        query = query.filter(Order.shop_type == shop_type)
    if order_type:
        query = query.filter(Order.order_type == order_type)
    if order_status is not None and order_status != -1:
        query = query.filter(Order.order_status == order_status)
    if keyword:
        query = query.filter(db.or_(
            Order.order_no.like(f'%{keyword}%'),
            Order.jd_order_no.like(f'%{keyword}%'),
            Order.product_info.like(f'%{keyword}%'),
            Order.produce_account.like(f'%{keyword}%'),
        ))
    elif jd_order_no:
        query = query.filter(Order.jd_order_no.like(f'%{jd_order_no}%'))
    if start_date:
        try:
            query = query.filter(Order.create_time >= datetime.strptime(start_date, '%Y-%m-%d'))
        except ValueError:
            pass
    if end_date:
        try:
            query = query.filter(Order.create_time <= datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
        except ValueError:
            pass

    def generate_csv():
        output = io.StringIO()
        output.write('\ufeff')  # UTF-8 BOM
        writer = csv.writer(output)
        writer.writerow(['京东订单号', '系统订单号', '店铺名称', '店铺类型', '订单类型', '订单状态',
                         '商品信息', '金额(元)', '数量', '充值账号', '创建时间'])
        yield output.getvalue()

        for o in query.order_by(Order.id.desc()).limit(10000).yield_per(200):
            row_buf = io.StringIO()
            csv.writer(row_buf).writerow([
                o.jd_order_no,
                o.order_no,
                o.shop.shop_name if o.shop else '',
                o.shop_type_label,
                o.order_type_label,
                o.order_status_label,
                o.product_info or '',
                f'{o.amount / 100:.2f}',
                o.quantity,
                o.produce_account or '',
                o.create_time.strftime('%Y-%m-%d %H:%M:%S') if o.create_time else '',
            ])
            yield row_buf.getvalue()

    filename = f'订单导出_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    return Response(
        generate_csv(),
        mimetype='text/csv; charset=utf-8-sig',
        headers={'Content-Disposition': f'attachment; filename*=UTF-8\'\'{filename}'}
    )

@order_bp.route('/detail/<int:order_id>')
@login_required
def order_detail(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        flash('订单不存在', 'danger')
        return redirect(url_for('order.order_list'))

    if not current_user.is_admin and not current_user.has_shop_permission(order.shop_id):
        flash('无权限查看此订单', 'danger')
        return redirect(url_for('order.order_list'))

    return render_template('order/detail.html', order=order)


@order_bp.route('/<int:order_id>/save-cards', methods=['POST'])
@login_required
def save_cards(order_id):
    """保存卡密信息"""
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify(success=False, message='订单不存在')
    
    if order.order_type != 2:
        return jsonify(success=False, message='该订单不是卡密订单')
    
    data = request.get_json()
    cards = data.get('cards', [])
    
    if len(cards) != order.quantity:
        return jsonify(success=False, message=f'卡密数量不匹配，需要{order.quantity}组')
    
    # 保存卡密
    order.set_card_info(cards)
    db.session.commit()
    
    logger.info(f"订单 {order.order_no} 保存了 {len(cards)} 组卡密")
    
    return jsonify(success=True, message=f'成功保存{len(cards)}组卡密')


@order_bp.route('/deliver-card/<int:order_id>', methods=['POST'])
@login_required
def deliver_card(order_id):
    """保存卡密并回调京东（手动发卡密）。

    请求体：{"cards": [{"cardNo": "xxx", "cardPwd": "xxx"}, ...]}
    """
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify(success=False, message='订单不存在')

    if not current_user.is_admin and not current_user.can_deliver:
        return jsonify(success=False, message='无操作权限'), 403
    if not current_user.has_shop_permission(order.shop_id):
        return jsonify(success=False, message='无操作权限'), 403

    if order.order_type != 2:
        return jsonify(success=False, message='该订单不是卡密订单')

    data = request.get_json() or {}
    cards = data.get('cards', [])

    if len(cards) != order.quantity:
        return jsonify(success=False, message=f'卡密数量不匹配，需要{order.quantity}组')

    order.set_card_info(cards)
    db.session.commit()

    shop = order.shop
    if not shop:
        return jsonify(success=False, message='店铺不存在')

    try:
        if shop.shop_type == 1:
            success, message = callback_game_card_deliver(shop, order, cards)
        else:
            success, message = callback_general_card_deliver(shop, order, cards)

        if success:
            order.order_status = 2
            order.notify_status = NOTIFY_STATUS_SUCCESS
            order.notify_time = datetime.now()
            db.session.commit()
            _log_operation(current_user, 'deliver_card', 'order', order.id,
                           f'手动发卡密：订单 {order.jd_order_no}，共{len(cards)}组')
            return jsonify(success=True, message='卡密发送成功')
        else:
            order.notify_status = NOTIFY_STATUS_FAILED
            db.session.commit()
            return jsonify(success=False, message=message)
    except Exception as e:
        logger.error(f"订单 {order.order_no} 发卡密失败：{e}")
        order.notify_status = NOTIFY_STATUS_FAILED
        db.session.commit()
        return jsonify(success=False, message=f'发卡密失败：{str(e)}')


@order_bp.route('/self-debug/<int:order_id>', methods=['POST'])
@login_required
def self_debug(order_id):
    """自助联调：设置订单状态（不触发回调）。

    请求体：{"status": "success"|"processing"|"failed"}
    """
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify(success=False, message='订单不存在')

    data = request.get_json() or {}
    status = data.get('status', '')

    status_map = {
        'success': (2, '已完成'),
        'processing': (1, '处理中'),
        'failed': (3, '已取消'),
    }
    if status not in status_map:
        return jsonify(success=False, message=f'无效状态：{status}')

    order_status, label = status_map[status]
    order.order_status = order_status
    db.session.commit()

    logger.info(f"订单 {order.order_no} 自助联调标记为{label}")
    return jsonify(success=True, message=f'订单已标记为{label}')


@order_bp.route('/notify-success/<int:order_id>', methods=['POST'])
@login_required
def notify_success(order_id):
    """通知京东订单成功"""
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify(success=False, message='订单不存在')

    # 权限检查
    if not current_user.is_admin and not current_user.can_deliver:
        return jsonify(success=False, message='无操作权限'), 403
    if not current_user.has_shop_permission(order.shop_id):
        return jsonify(success=False, message='无操作权限'), 403

    shop = order.shop
    if not shop:
        return jsonify(success=False, message='店铺不存在')
    
    # 如果是卡密订单，检查是否已填写卡密
    if order.order_type == 2:
        if not order.card_info_parsed:
            return jsonify(success=False, message='请先填写卡密信息')
    
    # 根据店铺类型和订单类型调用不同的回调接口
    try:
        if shop.shop_type == 1:
            # 游戏点卡平台
            if order.order_type == 1:
                success, message = callback_game_direct_success(shop, order)
            else:
                success, message = callback_game_card_deliver(shop, order, order.card_info_parsed)
        else:
            # 通用交易平台
            if order.order_type == 1:
                success, message = callback_general_success(shop, order)
            else:
                success, message = callback_general_card_deliver(shop, order, order.card_info_parsed)
        
        if success:
            order.order_status = 2
            order.notify_status = NOTIFY_STATUS_SUCCESS
            order.notify_time = datetime.now()
            db.session.commit()
            _log_operation(current_user, 'deliver', 'order', order.id,
                           f'对订单 {order.jd_order_no} 执行了通知成功操作')
            logger.info(f"订单 {order.order_no} 通知成功")
            return jsonify(success=True, message='通知成功')
        else:
            order.notify_status = NOTIFY_STATUS_FAILED
            db.session.commit()
            return jsonify(success=False, message=message)
    
    except Exception as e:
        logger.error(f"订单 {order.order_no} 通知失败：{e}")
        order.notify_status = NOTIFY_STATUS_FAILED
        db.session.commit()
        return jsonify(success=False, message=f'通知失败：{str(e)}')


@order_bp.route('/notify-refund/<int:order_id>', methods=['POST'])
@login_required
def notify_refund(order_id):
    """通知京东订单退款"""
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify(success=False, message='订单不存在')

    # 权限检查
    if not current_user.is_admin and not current_user.can_refund:
        return jsonify(success=False, message='无操作权限'), 403
    if not current_user.has_shop_permission(order.shop_id):
        return jsonify(success=False, message='无操作权限'), 403

    shop = order.shop
    if not shop:
        return jsonify(success=False, message='店铺不存在')
    
    # 检查是否可以退款
    if order.order_status in (3, 4):
        return jsonify(success=False, message='订单已退款或已取消')
    
    # 根据店铺类型调用对应的退款回调
    try:
        if shop.shop_type == 1:
            success, message = callback_game_refund(shop, order)
        else:
            success, message = callback_general_refund(shop, order)
        
        if success:
            order.order_status = 4  # 已退款
            order.notify_status = NOTIFY_STATUS_SUCCESS
            order.notify_time = datetime.now()
            db.session.commit()
            _log_operation(current_user, 'refund', 'order', order.id,
                           f'对订单 {order.jd_order_no} 执行了通知退款操作')
            logger.info(f"订单 {order.order_no} 退款通知成功")
            return jsonify(success=True, message='退款通知已发送')
        else:
            order.notify_status = NOTIFY_STATUS_FAILED
            db.session.commit()
            return jsonify(success=False, message=message)
    
    except Exception as e:
        logger.error(f"订单 {order.order_no} 退款通知失败：{e}")
        order.notify_status = NOTIFY_STATUS_FAILED
        db.session.commit()
        return jsonify(success=False, message=f'退款通知失败：{str(e)}')


@order_bp.route('/<int:order_id>/card91-deliver', methods=['POST'])
@login_required
def card91_deliver(order_id):
    """91卡券自动取卡发货。

    根据订单SKU匹配商品配置，从91卡券仓库自动提取卡密并回调京东。
    仅支持卡密订单（order_type=2）。
    """
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify(success=False, message='订单不存在')

    # 权限检查
    if not current_user.is_admin and not current_user.can_deliver:
        return jsonify(success=False, message='无操作权限'), 403
    if not current_user.has_shop_permission(order.shop_id):
        return jsonify(success=False, message='无操作权限'), 403

    if order.order_type != 2:
        return jsonify(success=False, message='91卡券只支持卡密订单类型')

    shop = order.shop
    if not shop:
        return jsonify(success=False, message='店铺不存在')
    if not shop.card91_api_key:
        return jsonify(success=False, message='该店铺未配置91卡券API密钥')

    # 根据SKU查找商品配置
    from app.models.product import Product
    from app.models.order_event import OrderEvent
    from app.services.card91 import card91_auto_deliver
    import json as json_mod

    product = None
    if order.sku_id:
        product = Product.query.filter_by(
            shop_id=shop.id, sku_id=order.sku_id, is_enabled=1, deliver_type=1
        ).first()
    if not product and order.product_info:
        # 按商品名称模糊匹配（截取前20字符防止过长，使用参数化查询）
        keyword = order.product_info[:20]
        product = Product.query.filter_by(
            shop_id=shop.id, deliver_type=1, is_enabled=1
        ).filter(Product.product_name.contains(keyword)).first()

    if not product:
        return jsonify(success=False, message='未找到匹配的91卡券商品配置，请先在商品管理中设置')

    # 从91卡券提卡
    ok, msg, cards = card91_auto_deliver(shop, order, product)

    # 记录提卡事件
    fetch_event = OrderEvent(
        order_id=order.id,
        order_no=order.order_no,
        event_type='card91_fetch',
        event_desc=f'91卡券提卡：{msg}',
        event_data=json_mod.dumps({'product_name': product.product_name,
                                    'card_type_id': product.card91_card_type_id,
                                    'quantity': order.quantity,
                                    'success': ok}, ensure_ascii=False),
        operator=current_user.username,
        result='success' if ok else 'failed',
    )
    db.session.add(fetch_event)

    if not ok:
        db.session.commit()
        return jsonify(success=False, message=msg)

    # 保存卡密到订单
    order.set_card_info(cards)
    db.session.commit()

    # 回调京东通知发货
    try:
        if shop.shop_type == 1:
            success, callback_msg = callback_game_card_deliver(shop, order, cards)
        else:
            success, callback_msg = callback_general_card_deliver(shop, order, cards)

        if success:
            order.order_status = 2
            order.deliver_time = datetime.now()
            order.notify_status = NOTIFY_STATUS_SUCCESS
            order.notify_time = datetime.now()

            # 记录发卡成功事件
            deliver_event = OrderEvent(
                order_id=order.id,
                order_no=order.order_no,
                event_type='card91_deliver',
                event_desc=f'91卡券发卡成功，共{len(cards)}张',
                event_data=json_mod.dumps({'cards_count': len(cards),
                                            'callback_msg': callback_msg}, ensure_ascii=False),
                operator=current_user.username,
                result='success',
            )
            db.session.add(deliver_event)
            db.session.commit()

            _log_operation(current_user, 'card91_deliver', 'order', order.id,
                           f'91卡券自动发卡：订单 {order.jd_order_no}，共{len(cards)}张')
            return jsonify(success=True, message=f'91卡券发卡成功，共{len(cards)}张卡密已发货')
        else:
            order.notify_status = NOTIFY_STATUS_FAILED

            # 记录发卡失败事件
            fail_event = OrderEvent(
                order_id=order.id,
                order_no=order.order_no,
                event_type='error',
                event_desc=f'91卡券回调失败：{callback_msg}',
                operator=current_user.username,
                result='failed',
            )
            db.session.add(fail_event)
            db.session.commit()
            return jsonify(success=False, message=f'卡密已提取但回调京东失败：{callback_msg}')

    except Exception as e:
        logger.error(f'91卡券发货回调异常：{e}')
        order.notify_status = NOTIFY_STATUS_FAILED
        db.session.commit()
        return jsonify(success=False, message=f'回调失败：{str(e)}')


@order_bp.route('/<int:order_id>/debug-success', methods=['POST'])
@login_required
def debug_success(order_id):
    """自助联调：标记订单为充值成功(不触发回调)"""
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify(success=False, message='订单不存在')
    
    # 更新订单状态为2(已完成)
    order.order_status = 2
    db.session.commit()
    
    logger.info(f"订单 {order.order_no} 自助联调标记为充值成功")
    return jsonify(success=True, message='订单已标记为充值成功')


@order_bp.route('/<int:order_id>/debug-processing', methods=['POST'])
@login_required
def debug_processing(order_id):
    """自助联调：标记订单为充值中"""
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify(success=False, message='订单不存在')
    
    # 更新订单状态为1(处理中)
    order.order_status = 1
    db.session.commit()
    
    logger.info(f"订单 {order.order_no} 自助联调标记为充值中")
    return jsonify(success=True, message='订单已标记为充值中')


@order_bp.route('/<int:order_id>/debug-failed', methods=['POST'])
@login_required
def debug_failed(order_id):
    """自助联调：标记订单为充值失败"""
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify(success=False, message='订单不存在')
    
    # 更新订单状态为3(已取消)
    order.order_status = 3
    db.session.commit()
    
    logger.info(f"订单 {order.order_no} 自助联调标记为充值失败")
    return jsonify(success=True, message='订单已标记为充值失败')


@order_bp.route('/batch-notify-success', methods=['POST'])
@login_required
def batch_notify_success():
    """批量通知成功"""
    if not current_user.is_admin and not current_user.can_deliver:
        return jsonify(success=False, message='无操作权限'), 403

    data = request.get_json() or {}
    order_ids = data.get('order_ids', [])
    if not order_ids:
        return jsonify(success=False, message='请选择订单')

    ok_list, fail_list = [], []
    for oid in order_ids[:100]:
        order = db.session.get(Order, oid)
        if not order:
            fail_list.append({'id': oid, 'reason': '订单不存在'})
            continue
        if not current_user.has_shop_permission(order.shop_id):
            fail_list.append({'id': oid, 'reason': '无店铺权限'})
            continue
        if order.order_status not in (0, 1):
            fail_list.append({'id': oid, 'reason': '状态不符'})
            continue
        if order.order_type != 1:
            fail_list.append({'id': oid, 'reason': '非直充订单'})
            continue
        shop = order.shop
        if not shop:
            fail_list.append({'id': oid, 'reason': '店铺不存在'})
            continue
        try:
            if shop.shop_type == 1:
                success, msg = callback_game_direct_success(shop, order)
            else:
                success, msg = callback_general_success(shop, order)
            if success:
                order.order_status = 2
                order.notify_status = NOTIFY_STATUS_SUCCESS
                order.notify_time = datetime.now()
                db.session.commit()
                _log_operation(current_user, 'deliver', 'order', order.id,
                               f'批量通知成功：订单 {order.jd_order_no}')
                ok_list.append(oid)
            else:
                fail_list.append({'id': oid, 'reason': msg})
        except Exception as e:
            fail_list.append({'id': oid, 'reason': str(e)})

    return jsonify(success=True, ok_count=len(ok_list), fail_count=len(fail_list), fails=fail_list)


@order_bp.route('/<int:order_id>/detail-html', methods=['GET'])
@login_required
def order_detail_html(order_id):
    """返回订单详情HTML片段（用于弹窗），包含订单事件日志。"""
    order = db.session.get(Order, order_id)
    if not order:
        return '<div class="alert alert-error">订单不存在</div>', 404

    # 加载订单事件日志（按时间倒序）
    try:
        from app.models.order_event import OrderEvent
        events = OrderEvent.query.filter_by(order_id=order.id).order_by(
            OrderEvent.create_time.desc()
        ).limit(50).all()
    except Exception:
        events = []

    # 渲染详情页模板的主体部分（不包含外层布局）
    return render_template('order/detail_modal.html', order=order, events=events)
