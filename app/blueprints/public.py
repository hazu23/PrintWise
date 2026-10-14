"""Pages anyone can open without logging in."""
from flask import Blueprint, abort, render_template

from app.models import PrintShop

bp = Blueprint("public", __name__)


@bp.route("/")
def index():
    shops = PrintShop.filter(order_by="name ASC", is_active=1)
    return render_template("public/index.html", shops=shops)


@bp.route("/shops")
def shops():
    shops = PrintShop.filter(order_by="name ASC", is_active=1)
    return render_template("public/shops.html", shops=shops)


@bp.route("/shops/<int:shop_id>")
def shop_detail(shop_id):
    shop = PrintShop.get(shop_id)
    if shop is None or not shop.is_active:
        abort(404)
    return render_template("public/shop_detail.html", shop=shop, services=shop.services(only_active=True))
