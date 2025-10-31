from .models import Cart

def cart_meta(request):
    count = 0
    if request.user.is_authenticated:
        # Robust: works even if the user has no Customer row yet
        cart = Cart.objects.filter(customer__user=request.user).first()
        if cart:
            count = cart.count  # your @property on Cart
    else:
        count = request.session.get("cart_count", 0)
    return {"cart_count": count}
