from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from .models import Product, Category
from .forms import UserSignupForm, CustomerForm, EmailLoginForm

# Create your views here.

def home(request, slug=None):
    products = Product.objects.select_related('category').all()

    # PARENTS ONLY (the 12 main categories)
    categories = (
        Category.objects
        .filter(parent__isnull=True)   # <— only top-level
        .order_by('name')[:12]
    )

    q = (request.GET.get('q') or '').strip()
    sort = (request.GET.get('sort') or '').strip()

    category = None
    if slug:
        category = get_object_or_404(Category, slug=slug)
        products = products.filter(category=category)

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
        'cart_count': request.session.get('cart_count', 0),
        'category': category,
    }
    return render(request, 'storefront/home.html', context)

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