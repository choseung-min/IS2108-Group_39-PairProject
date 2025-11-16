from storefront.models import Product
from django.db.models import F


def low_stock_count(request):
    count = Product.objects.filter(
        is_active=True, stock__lt=F("reorder_threshold")
    ).count()
    return {"low_stock_count": count}


from .models import Cart


def cart_meta(request):
    count = 0
    if request.user.is_authenticated:
        cart = Cart.objects.filter(customer__user=request.user).first()
        if cart:
            count = cart.count
    else:
        count = request.session.get("cart_count", 0)
    return {"cart_count": count}
