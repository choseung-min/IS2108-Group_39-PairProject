from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.db import transaction
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from .models import Product, Category, Cart, CartItem, Customer
from .forms import UserSignupForm, CustomerForm, EmailLoginForm

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
        'cart_count': _get_cart_for(request.user).count if request.user.is_authenticated else request.session.get("cart_count", 0),
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
            return redirect("home")
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
            return redirect("home")
    else:
        form = EmailLoginForm()
    return render(request, "storefront/login.html", {"form": form})

def logout_view(request):
    logout(request)
    return redirect('home')

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
   