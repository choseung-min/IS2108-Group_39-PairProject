from django.shortcuts import render
from .models import Product, Category
from django.db.models import Q

def home(request):
    return render(request, 'adminpanel/home_page.html')

def products(request):
    products = Product.objects.filter(is_active=True)
    query = request.GET.get('q')
    category_id = int(request.GET.get('category')) if request.GET.get('category') else None

    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(category__name__icontains=query))

    if category_id:
        products = products.filter(category_id=category_id)

    categories = Category.objects.all().only("id", "name")

    context = {'products': products, 'query': query, 'category_id': category_id, 'categories': categories}

    return render(request, 'adminpanel/products/product_catalogue.html', context)

def restock(request):
    return render(request, 'adminpanel/restock/restock_dashboard.html')

def customers(request):
    return render(request, 'adminpanel/customers/customer_records.html')