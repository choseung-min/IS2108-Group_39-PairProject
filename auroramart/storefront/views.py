from django.shortcuts import render, get_object_or_404
from .models import Product, Category

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
        'products': products[:50],
        'q': q,
        'sort': sort,
        'cart_count': request.session.get('cart_count', 0),
        'category': category,
    }
    return render(request, 'storefront/home.html', context)
