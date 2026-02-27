import json
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.extensions import db
from app.models.shop import Shop

settings_bp = Blueprint('settings', __name__)
logger = logging.getLogger(__name__)


@settings_bp.route('/settings')
@login_required
def index():
    """配置首页：店铺列表"""
    shops = Shop.query.all()
    return render_template('settings/index.html', shops=shops)


@settings_bp.route('/settings/shops/new', methods=['GET', 'POST'])
@login_required
def shop_new():
    """新建店铺"""
    if request.method == 'POST':
        shop = Shop(name=request.form.get('name', ''))
        _update_shop_from_form(shop, request.form)
        db.session.add(shop)
        db.session.commit()
        flash('店铺创建成功', 'success')
        return redirect(url_for('settings.index'))
    return render_template('settings/shop_form.html', shop=None)


@settings_bp.route('/settings/shops/<int:shop_id>', methods=['GET', 'POST'])
@login_required
def shop_edit(shop_id):
    """编辑店铺"""
    shop = Shop.query.get_or_404(shop_id)
    if request.method == 'POST':
        shop.name = request.form.get('name', shop.name)
        _update_shop_from_form(shop, request.form)
        db.session.commit()
        flash('店铺配置已保存', 'success')
        return redirect(url_for('settings.shop_edit', shop_id=shop_id))
    return render_template('settings/shop_form.html', shop=shop)


@settings_bp.route('/settings/shops/<int:shop_id>/delete', methods=['POST'])
@login_required
def shop_delete(shop_id):
    """删除店铺"""
    shop = Shop.query.get_or_404(shop_id)
    db.session.delete(shop)
    db.session.commit()
    flash('店铺已删除', 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/shops/<int:shop_id>/address', methods=['GET', 'POST'])
@login_required
def default_address(shop_id):
    """默认地址配置"""
    shop = Shop.query.get_or_404(shop_id)
    if request.method == 'POST':
        address_data = {
            'name': request.form.get('name', ''),
            'phone': request.form.get('phone', ''),
            'province': request.form.get('province', ''),
            'city': request.form.get('city', ''),
            'district': request.form.get('district', ''),
            'address': request.form.get('address', ''),
            'zip_code': request.form.get('zip_code', '')
        }
        shop.default_address = json.dumps(address_data, ensure_ascii=False)
        db.session.commit()
        flash('默认地址已保存', 'success')
        return redirect(url_for('settings.default_address', shop_id=shop_id))

    address = {}
    if shop.default_address:
        try:
            address = json.loads(shop.default_address)
        except Exception:
            pass
    return render_template('settings/default_address.html', shop=shop, address=address)


def _update_shop_from_form(shop, form):
    """从表单更新店铺配置"""
    # 游戏点卡配置
    shop.game_customer_id = form.get('game_customer_id', '')
    shop.game_md5_secret = form.get('game_md5_secret', '')
    shop.game_api_url = form.get('game_api_url', '')
    shop.game_direct_callback_url = form.get('game_direct_callback_url', '')
    shop.game_card_callback_url = form.get('game_card_callback_url', '')

    # 通用交易配置
    shop.general_vendor_id = form.get('general_vendor_id', '')
    shop.general_md5_secret = form.get('general_md5_secret', '')
    shop.general_aes_secret = form.get('general_aes_secret', '')
    shop.general_callback_url = form.get('general_callback_url', '')

    # 阿奇索配置
    shop.agiso_enabled = int(form.get('agiso_enabled', 0))
    shop.agiso_app_id = form.get('agiso_app_id', '')
    shop.agiso_app_secret = form.get('agiso_app_secret', '')
    shop.agiso_access_token = form.get('agiso_access_token', '')
    shop.agiso_host = form.get('agiso_host', '')
    shop.agiso_port = form.get('agiso_port', '')

    # 其他配置
    shop.auto_deliver = int(form.get('auto_deliver', 0))
