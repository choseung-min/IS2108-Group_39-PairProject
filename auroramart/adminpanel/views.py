from django.contrib import messages
from django.shortcuts import redirect, render
from .models import Product, Category
from django.db.models import Q
from django.core.paginator import Paginator
from .forms import ProductForm

def home(request):
    return render(request, 'adminpanel/home_page.html')

def products(request):
    products = Product.objects.filter(is_active=True)
    query = request.GET.get('q')
    main_categories = Category.objects.filter(parent__isnull=True)
    selected_categories = [c for c in request.GET.getlist("category") if c.strip() != ""]

    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(category__name__icontains=query))

    if selected_categories:
        products = products.filter(Q(category_id__in=selected_categories) | Q(category__parent_id__in=selected_categories))
    
    paginator = Paginator(products, 20)
    page_num = request.GET.get('page')
    page_obj = paginator.get_page(page_num)

    context = {'page_obj': page_obj, 'products': page_obj.object_list, 'query': query, 'selected_categories': selected_categories, 'main_categories': main_categories}

    return render(request, 'adminpanel/products/product_catalogue.html', context)

def add_product(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        
        if form.is_valid():
            form.save()
            messages.success(request, "New product \"{name}\" added successfully!".format(name=form.cleaned_data["name"]))
            return redirect("add_product")
        
        else:
            messages.error(request, "Please correct the errors below.")
    
    else:
        form = ProductForm()

    return render(request, "adminpanel/products/add_product.html", {"form": form})

def restock(request):
    return render(request, 'adminpanel/restock/restock_dashboard.html')

def customers(request):
    return render(request, 'adminpanel/customers/customer_records.html')
