"""商品管理路由模块。

提供商品的增删改查功能，支持：
- 为每个店铺配置商品和对应发货方式
- 从91卡券平台获取卡种列表
- 手动或通过91卡券自动发货配置

子账号权限：只能管理自己授权店铺的商品。
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models.shop import Shop
from app.models.product import Product
import logging
import json

logger = logging.getLogger(__name__)

product_bp = Blueprint('product', __name__)


def _check_shop_access(shop_id):
    """检查当前用户是否有权限访问指定店铺。"""
    shop = db.session.get(Shop, shop_id)
    if not shop:
        return None
    if not current_user.is_admin and not current_user.has_shop_permission(shop_id):
        return None
    return shop


def _get_accessible_shops():
    """获取当前用户可访问的店铺列表。"""
    if current_user.is_admin:
        return Shop.query.filter_by(is_enabled=1).order_by(Shop.shop_name).all()
    permitted_ids = current_user.get_permitted_shop_ids()
    if not permitted_ids:
        return []
    return Shop.query.filter(Shop.id.in_(permitted_ids), Shop.is_enabled == 1).order_by(Shop.shop_name).all()


def _log_operation(action, target_type, target_id, detail):
    """记录操作日志。"""
    try:
        from app.models.operation_log import OperationLog
        log = OperationLog(
            user_id=current_user.id,
            username=current_user.username,
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


@product_bp.route('/')
@login_required
def product_list():
    """商品列表页。"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    query = Product.query
    if not current_user.is_admin:
        permitted_ids = current_user.get_permitted_shop_ids()
        if permitted_ids:
            query = query.filter(Product.shop_id.in_(permitted_ids))
        else:
            query = query.filter(db.false())
    shop_id = request.args.get('shop_id', type=int)
    deliver_type = request.args.get('deliver_type', type=int)
    keyword = request.args.get('keyword', '').strip()
    FILTER_ALL = -1
    if shop_id:
        query = query.filter(Product.shop_id == shop_id)
    if deliver_type is not None and deliver_type != FILTER_ALL:
        query = query.filter(Product.deliver_type == deliver_type)
    if keyword:
        query = query.filter(
            db.or_(
                Product.product_name.like(f'%{keyword}%'),
                Product.sku_id.like(f'%{keyword}%'),
                Product.sku_name.like(f'%{keyword}%'),
                Product.jd_product_id.like(f'%{keyword}%'),
            )
        )
    pagination = query.order_by(Product.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    shops = _get_accessible_shops()
    return render_template('product/list.html',
                           products=pagination.items,
                           pagination=pagination,
                           shops=shops)


@product_bp.route('/create', methods=['GET', 'POST'])
@login_required
def product_create():
    """创建商品配置。"""
    shops = _get_accessible_shops()
    if request.method == 'POST':
        shop_id = request.form.get('shop_id', type=int)
        if not shop_id:
            flash('请选择店铺', 'danger')
            return render_template('product/form.html', product=None, shops=shops)
        shop = _check_shop_access(shop_id)
        if not shop:
            flash('无权限操作此店铺', 'danger')
            return render_template('product/form.html', product=None, shops=shops)
        product = Product(shop_id=shop_id)
        _fill_product_fields(product, request.form)
        db.session.add(product)
        try:
            db.session.commit()
            _log_operation('create_product', 'product', product.id,
                           f'创建商品：{product.product_name}（店铺：{shop.shop_name}）')
            flash('商品配置创建成功', 'success')
            return redirect(url_for('product.product_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败：{e}', 'danger')
    default_shop_id = request.args.get('shop_id', type=int)
    return render_template('product/form.html', product=None, shops=shops,
                           default_shop_id=default_shop_id)


@product_bp.route('/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def product_edit(product_id):
    """编辑商品配置。"""
    product = db.session.get(Product, product_id)
    if not product:
        flash('商品不存在', 'danger')
        return redirect(url_for('product.product_list'))
    if not current_user.is_admin and not current_user.has_shop_permission(product.shop_id):
        flash('无权限操作此商品', 'danger')
        return redirect(url_for('product.product_list'))
    shops = _get_accessible_shops()
    if request.method == 'POST':
        _fill_product_fields(product, request.form)
        try:
            db.session.commit()
            _log_operation('edit_product', 'product', product.id,
                           f'编辑商品：{product.product_name}')
            flash('商品配置更新成功', 'success')
            return redirect(url_for('product.product_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败：{e}', 'danger')
    return render_template('product/form.html', product=product, shops=shops)


@product_bp.route('/delete/<int:product_id>', methods=['POST'])
@login_required
def product_delete(product_id):
    """删除商品配置。"""
    product = db.session.get(Product, product_id)
    if not product:
        flash('商品不存在', 'danger')
        return redirect(url_for('product.product_list'))
    if not current_user.is_admin and not current_user.has_shop_permission(product.shop_id):
        flash('无权限操作此商品', 'danger')
        return redirect(url_for('product.product_list'))
    name = product.product_name
    pid = product.id
    db.session.delete(product)
    db.session.commit()
    _log_operation('delete_product', 'product', pid, f'删除商品：{name}')
    flash('商品配置已删除', 'success')
    return redirect(url_for('product.product_list'))


@product_bp.route('/api/card91-types/<int:shop_id>', methods=['GET'])
@login_required
def api_card91_types(shop_id):
    """获取91卡券卡种列表（AJAX接口）。"""
    shop = _check_shop_access(shop_id)
    if not shop:
        return jsonify(success=False, message='店铺不存在或无权限')
    if not shop.card91_api_key:
        return jsonify(success=False, message='该店铺未配置91卡券API密钥，请先在店铺配置中填写')
    from app.services.card91 import card91_get_card_types
    ok, msg, card_types = card91_get_card_types(shop)
    return jsonify(success=ok, message=msg, data=card_types)


@product_bp.route('/api/card91-stock/<int:shop_id>/<card_type_id>', methods=['GET'])
@login_required
def api_card91_stock(shop_id, card_type_id):
    """查询91卡券指定卡种库存（AJAX接口）。"""
    shop = _check_shop_access(shop_id)
    if not shop:
        return jsonify(success=False, message='店铺不存在或无权限')
    from app.services.card91 import card91_get_stock
    ok, msg, stock = card91_get_stock(shop, card_type_id)
    return jsonify(success=ok, message=msg, stock=stock)


@product_bp.route('/api/shop-card91-config/<int:shop_id>', methods=['GET'])
@login_required
def api_shop_card91_config(shop_id):
    """获取店铺的91卡券配置（用于商品管理页面弹窗显示）。"""
    shop = _check_shop_access(shop_id)
    if not shop:
        return jsonify(success=False, message='店铺不存在或无权限')
    return jsonify(success=True, data={
        'card91_api_url': shop.card91_api_url or '',
        'card91_api_key': shop.card91_api_key or '',
        'has_secret': bool(shop.card91_api_secret),
    })


@product_bp.route('/api/save-shop-card91/<int:shop_id>', methods=['POST'])
@login_required
def api_save_shop_card91(shop_id):
    """从商品管理页面保存店铺的91卡券API配置。"""
    shop = _check_shop_access(shop_id)
    if not shop:
        return jsonify(success=False, message='店铺不存在或无权限')
    data = request.get_json() or {}
    shop.card91_api_url = data.get('card91_api_url', '').strip() or None
    shop.card91_api_key = data.get('card91_api_key', '').strip() or None
    new_secret = data.get('card91_api_secret', '').strip()
    if new_secret:
        shop.card91_api_secret = new_secret
    try:
        db.session.commit()
        _log_operation('save_card91_config', 'shop', shop.id,
                       f'从商品管理页面更新店铺91卡券配置：{shop.shop_name}')
        return jsonify(success=True, message='91卡券配置保存成功')
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=f'保存失败：{e}')


@product_bp.route('/api/parse-jd-sku', methods=['POST'])
@login_required
def api_parse_jd_sku():
    """解析用户从京东商品页面执行JS后复制的SKU数据。"""
    data = request.get_json() or {}
    raw_json = data.get('raw_json', '').strip()
    if not raw_json:
        return jsonify(success=False, message='数据为空，请先在京东商品页执行脚本')
    try:
        parsed = json.loads(raw_json)
    except Exception:
        return jsonify(success=False, message='JSON格式错误，请重新复制执行结果')
    sku_id = str(parsed.get('skuId') or '').strip()
    sku_name = str(parsed.get('skuName') or '').strip()
    skus_raw = parsed.get('skus', [])
    if not sku_id:
        return jsonify(success=False, message='未找到skuId，请确认在正确的京东商品页执行了脚本')

    def clean_spec(spec):
        spec = spec.strip()
        half = len(spec) // 2
        if half > 0 and spec[:half] == spec[half:]:
            return spec[:half]
        return spec

    skus = []
    for s in skus_raw:
        sid = str(s.get('skuId') or '').strip()
        spec = clean_spec(str(s.get('spec') or ''))
        if sid:
            skus.append({'skuId': sid, 'spec': spec})

    return jsonify(
        success=True,
        skuId=sku_id,
        skuName=sku_name,
        skus=skus,
        message=f'成功获取商品信息，共{len(skus)}个规格'
    )


def _fill_product_fields(product, form):
    """从表单数据填充商品字段。"""
    product.product_name = form.get('product_name', '').strip()
    product.jd_product_id = form.get('jd_product_id', '').strip() or None
    product.sku_id = form.get('sku_id', '').strip() or None
    product.sku_name = form.get('sku_name', '').strip() or None
    product.deliver_type = int(form.get('deliver_type', 0))
    product.card91_card_type_id = form.get('card91_card_type_id', '').strip() or None
    product.card91_card_type_name = form.get('card91_card_type_name', '').strip() or None
    product.card91_plan_id = form.get('card91_plan_id', '').strip() or None
    product.direct_charge_api_type = form.get('direct_charge_api_type', '').strip() or None
    product.is_enabled = int(form.get('is_enabled', 1))
    product.remark = form.get('remark', '').strip() or None
