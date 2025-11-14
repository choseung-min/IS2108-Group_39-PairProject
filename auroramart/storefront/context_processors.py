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
