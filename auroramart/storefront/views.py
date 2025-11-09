from decimal import Decimal
from typing import List, Tuple
from django.db import transaction
from django.db.models import Q
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import UserSignupForm, CustomerForm, EmailLoginForm, AddressForm, PaymentForm, ProfileForm
from .models import Product, Category, Cart, CartItem, Customer, Order, OrderItem

# Create your views here.

#Home / Product Listing View
def home(request, slug=None):
    products = Product.objects.select_related('category').all()

    # PARENTS ONLY (the 12 main categories)
    categories = (
        Category.objects
        .filter(parent__isnull=True)  
        .order_by('name')[:12]
    )

    q = (request.GET.get('q') or '').strip()
    sort = (request.GET.get('sort') or '').strip()

    category = None
    if slug:
        category = get_object_or_404(Category, slug=slug)
        products = products.filter(Q(category=category) | Q(category__parent=category))

    if q:
        products = products.filter(name__icontains=q)

    if sort == 'price_asc':
        products = products.order_by('price', '-rating', 'name')
    elif sort == 'price_desc':
        products = products.order_by('-price', '-rating', 'name')
    elif sort == 'new':
        products = products.order_by('-id')
    else:
        products = products.order_by('-rating', 'name')

    context = {
        'categories': categories,
        'products': products[:500],
        'q': q,
        'sort': sort,
        'category': category,
    }
    return render(request, 'storefront/home.html', context)

#Signup / Login / Logout Views
def signup(request):
    # Handle GET (empty form) vs POST (submitted form)
    if request.method == "POST":
        uform = UserSignupForm(request.POST)
        cform = CustomerForm(request.POST)
        if uform.is_valid() and cform.is_valid():
            # 1️⃣ Create the Django User
            user = uform.save()  
            
            # 2️⃣ Create the Customer linked to that User
            customer = cform.save(user=user)
            
            # 3️⃣ Auto-login the new user
            login(request, user)

            # 4️⃣ Redirect to homepage after success
            return redirect("home2")
    else:
        uform = UserSignupForm()
        cform = CustomerForm()

    # Render the signup page
    return render(request, "storefront/signup.html", {"uform": uform, "cform": cform})

def login_view(request):
    if request.method == "POST":
        form = EmailLoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data["user"]
            login(request, user)
            
            # Check for 'next' parameter first (with security validation)
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url and url_has_allowed_host_and_scheme(
                next_url, 
                allowed_hosts={request.get_host()}, 
                require_https=request.is_secure()
            ):
                return redirect(next_url)
            
            # Check if user is admin/staff and redirect accordingly
            if user.is_staff or user.is_superuser:
                return redirect("/adminpanel/")  # Redirect to admin panel
            else:
                return redirect("home2")  # Redirect to storefront
    else:
        form = EmailLoginForm()
    return render(request, "storefront/login.html", {"form": form})

def logout_view(request):
    logout(request)
    return redirect('home2')

#Cart Views
def cart_guest(request):
    return render(request, 'storefront/cart_guest.html')

def _get_customer_for(user):
    return get_object_or_404(Customer, user=user)

def _get_cart_for(user):
    customer = _get_customer_for(user)
    cart, _ = Cart.objects.get_or_create(customer=customer)
    return cart

def product_detail(request, slug):
    p = get_object_or_404(Product, slug=slug, is_active=True)
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect('login')
        qty = max(1, int(request.POST.get('quantity', '1') or 1))
        with transaction.atomic():
            cart = _get_cart_for(request.user)
            item, created = CartItem.objects.select_for_update().get_or_create(
                cart=cart, product=p, defaults={'quantity':qty, 'price_snapshot': p.price})
            if not created:
                item.quantity += qty
                if item.price_snapshot is None:
                    item.price_snapshot = p.price
            item.save(update_fields=['quantity', 'price_snapshot'])
        request.session['cart_count'] = cart.count
        return redirect('cart')
    return render(request, 'storefront/product_detail.html', {'product': p})

@login_required
def cart_add(request, product_id):
    p = get_object_or_404(Product, pk=product_id, is_active=True)
    cart = _get_cart_for(request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=p, defaults={'price_snapshot': p.price})
    if not created:
        item.quantity += 1
        if item.price_snapshot is None:
            item.price_snapshot = p.price
        item.save(update_fields=['quantity', 'price_snapshot'])
    request.session['cart_count'] = cart.count
    return redirect('cart')

def cart_view(request):
    if not request.user.is_authenticated:
        return render(request, 'storefront/cart_guest.html')
    
    cart = _get_cart_for(request.user)
    items = cart.items.select_related('product').all()
    return render(request, 'storefront/cart.html', {'cart': cart, 'items': items})

@login_required
def cart_update(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__customer__user=request.user)
    action = request.POST.get('action')
    if action == "inc":
        item.quantity += 1
        item.save(update_fields=['quantity'])
    elif action == "dec":
        item.quantity = max(1, item.quantity - 1)
        item.save(update_fields=['quantity'])
    request.session['cart_count'] = item.cart.count
    return redirect('cart')

@login_required
def cart_remove(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__customer__user=request.user)
    cart = item.cart
    item.delete()
    request.session['cart_count'] = cart.count
    return redirect('cart')

#checkout views
SESSION_KEY = 'checkout'

def _reprice_and_check_stock(cart_items) -> Tuple[bool, List[str], list, Decimal]:
    ok, errs, priced = True, [], []
    subtotal = Decimal("0.00")

    # Pull product inline, avoid repeated queries
    for ci in cart_items.select_related("product"):
        p, q = ci.product, ci.quantity

        # Stock check
        if p.stock < q:
            ok = False
            errs.append(f"{p.name}: only {p.stock} left in stock.")
            continue

        unit = p.price  # current price (DecimalField)
        line = unit * q
        priced.append((ci, unit, line))
        subtotal += line

    return ok, errs, priced, subtotal

def _compose_delivery_address(addr: str, city_state: str, postal: str) -> str:
    """Single string to store on Order.delivery_address"""
    lines = [addr.strip()]
    tail = " ".join(x for x in [city_state.strip(), postal.strip()] if x)
    if tail:
        lines.append(tail)
    return "\n".join(lines).strip()

@login_required
def checkout_address_view(request):
    cart = get_object_or_404(Cart, customer__user=request.user)
    items = CartItem.objects.filter(cart=cart)
    if not items.exists():
        messages.info(request, "Your cart is empty. Add items before checking out.")
        return redirect('cart')
    
    customer = request.user.customer

    initial = {
        "address": getattr(customer, "address", "") or "",
        "city_state": getattr(customer, "city_state", "") or "",
        "postal_code": getattr(customer, "postal_code", "") or "",
    }

    if (sess := request.session.get(SESSION_KEY)):
        initial.update({
            "address": sess.get("address", initial["address"]),
            "city_state": sess.get("city_state", initial["city_state"]),
            "postal_code": sess.get("postal_code", initial["postal_code"]),
        })
    
    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            # Save to session
            request.session[SESSION_KEY] = {
                "address": data["address"],
                "city_state": data["city_state"],
                "postal_code": data["postal_code"],
            }
            request.session.modified = True

            if data.get("save_to_profile"):
                customer.address = data["address"]
                customer.city_state = data["city_state"]
                customer.postal_code = data["postal_code"]
                customer.save(update_fields=["address", "city_state", "postal_code"])

            return redirect('checkout_payment')
        messages.error(request, "Please fix the address fields.")
    else:
        form = AddressForm(initial=initial)

    ok, errs, priced, subtotal = _reprice_and_check_stock(items)
    shipping_fee = Decimal('0.00')
    tax = Decimal('0.00')
    total = subtotal + shipping_fee + tax

    context = {
        "form": form,
        "cart_items": items.select_related('product'),
        "subtotal": subtotal,
        "shipping_fee": shipping_fee,
        "tax": tax,
        "total": total,
    }
    return render(request, 'storefront/checkout_address.html', context)

@login_required
@transaction.atomic
def checkout_payment_view(request):
    sess = request.session.get(SESSION_KEY)
    if not sess:
        messages.warning(request, "Please provide a delivery address before proceeding to payment.")
        return redirect('checkout_address')
    
    cart = _get_cart_for(request.user)
    items = CartItem.objects.filter(cart=cart)
    if not items.exists():
        messages.info(request, "Your cart is empty. Add items before checking out.")
        return redirect('cart')
    
    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            # Reprice and stock check
            ok, errs, priced, subtotal = _reprice_and_check_stock(items)
            if not ok:
                for e in errs:
                    messages.error(request, e)
                return redirect('checkout_address')

            shipping_fee = Decimal('0.00')
            tax = Decimal('0.00')
            total = subtotal + shipping_fee + tax

            delivery_address_text = _compose_delivery_address(
                sess["address"], sess.get("city_state", ""), sess["postal_code"]
            )

            # Create Order
            order = Order.objects.create(
                customer=request.user.customer,
                status = f"Pending ({form.cleaned_data['payment_method']})",
                total_amount=total,
                delivery_address=delivery_address_text,
            )

            # Create OrderItems and adjust stock
            for ci, unit_price, line_total in priced:
                OrderItem.objects.create(
                    order=order,
                    product=ci.product,
                    quantity=ci.quantity,
                    price_at_purchase=unit_price,
                )
                # Deduct stock
                ci.product.stock -= ci.quantity
                ci.product.save(update_fields=['stock'])

            # Clear cart
            items.delete()
            request.session.pop(SESSION_KEY, None)
            
            return redirect('order_success', order_id=order.id)
        messages.error(request, "Please select a valid payment method.")
    else:
        form = PaymentForm()
    
    ok, errs, priced, subtotal = _reprice_and_check_stock(items)
    shipping_fee = Decimal('0.00')
    tax = Decimal('0.00')
    total = subtotal + shipping_fee + tax

    addr_preview = _compose_delivery_address(
        sess["address"], sess.get("city_state", ""), sess["postal_code"]
    )
    
    context = {
        "form": form,
        "addr_text": addr_preview,
        "cart_items": items.select_related('product'),
        "subtotal": subtotal,
        "shipping_fee": shipping_fee,
        "tax": tax,
        "total": total,
    }
    return render(request, 'storefront/checkout_payment.html', context)

@login_required
def order_success_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer__user=request.user)
    return render(request, 'storefront/order_success.html', {'order': order})

#view profile views
@login_required
def profile_view(request):
    if request.method == "POST":
        form = ProfileForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("account")
        messages.error(request, "Please correct the errors below.")
    else:
        form = ProfileForm(request.user)

    orders = Order.objects.filter(customer=request.user.customer).order_by("-order_date")[:5]
    return render(request, "storefront/account.html", {"form": form, "orders": orders})

@login_required
def orders_list_view(request):
    orders = Order.objects.filter(customer=request.user.customer).order_by('-order_date')
    return render(request, 'storefront/orders_list.html', {"orders": orders})

@login_required
def order_detail_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user.customer)
    items = OrderItem.objects.filter(order=order).select_related('product')
    
    context = {
        "order": order,
        "items": items,
    }

    return render(request, 'storefront/order_detail.html', context)

@login_required
@transaction.atomic
def reorder_order_view(request, order_id):
    """Add all items from a previous order back into the cart."""
    order = get_object_or_404(Order, id=order_id, customer=request.user.customer)
    cart = _get_cart_for(request.user)

    for oi in OrderItem.objects.filter(order=order).select_related('product'):
        ci, created = CartItem.objects.get_or_create(
            cart=cart,
            product=oi.product,
            defaults={'quantity': oi.quantity, 'price_snapshot': oi.price_at_purchase}
        )
        if not created:
            ci.quantity += oi.quantity
            if ci.price_snapshot is None:
                ci.price_snapshot = oi.price_at_purchase
            ci.save(update_fields=['quantity', 'price_snapshot'])
    request.session['cart_count'] = cart.count
    return redirect('cart')

