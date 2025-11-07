from urllib import request
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from storefront.models import Product, Category
from django.db.models import Q, F, ExpressionWrapper, FloatField
from django.core.paginator import Paginator
from .forms import ProductForm


def home(request):
    return render(request, "adminpanel/home_page.html")


def products(request):
    products = Product.objects.all()
    query = request.GET.get("q")
    main_categories = Category.objects.filter(parent__isnull=True)
    selected_categories = [
        c for c in request.GET.getlist("category") if c.strip() != ""
    ]
    status_filter = request.GET.get("status_filter")
    stock_filter = request.GET.get("stock_filter")
    rating_filter = request.GET.get("rating_filter")
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")
    sort = request.GET.get("sort")
    query_params = request.GET.copy()
    page = query_params.pop("page", [None])[0]
    query_string = query_params.urlencode()

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
        )

    if selected_categories:
        products = products.filter(
            Q(category_id__in=selected_categories)
            | Q(category__parent_id__in=selected_categories)
        )

    if status_filter == "active":
        products = products.filter(is_active=True)
    elif status_filter == "inactive":
        products = products.filter(is_active=False)

    if stock_filter:
        if stock_filter == "healthy":
            products = products.filter(stock__gt=F("reorder_threshold"))
        elif stock_filter == "low":
            products = products.filter(stock__lte=F("reorder_threshold"), stock__gt=0)
        elif stock_filter == "out":
            products = products.filter(stock=0)

    if rating_filter:
        min_rating = int(rating_filter)
        products = products.filter(rating__gte=min_rating)

    if min_price and max_price:
        min_val = float(min_price)
        max_val = float(max_price)

        if min_val > max_val:
            messages.error(
                request, "Minimum price cannot be greater than maximum price."
            )
        else:
            products = products.filter(price__gte=min_val, price__lte=max_val)

    else:
        if min_price:
            products = products.filter(price__gte=float(min_price))
        if max_price:
            products = products.filter(price__lte=float(max_price))

    sort_fields = [
        "name",
        "-name",
        "price",
        "-price",
        "rating",
        "-rating",
        "stock",
        "-stock",
        "is_active",
        "-is_active",
    ]
    if sort in sort_fields:
        products = products.order_by(sort)

    paginator = Paginator(products, 15)
    page_num = request.GET.get("page")
    page_obj = paginator.get_page(page_num)

    low_stock_count = Product.objects.filter(stock__lte=F("reorder_threshold")).count()

    context = {
        "page_obj": page_obj,
        "products": page_obj.object_list,
        "query": query,
        "selected_categories": selected_categories,
        "main_categories": main_categories,
        "status_filter": status_filter,
        "stock_filter": stock_filter,
        "rating_filter": rating_filter,
        "min_price": min_price,
        "max_price": max_price,
        "sort": sort,
        "query_string": query_string,
        "low_stock_count": low_stock_count,
    }

    return render(request, "adminpanel/products/product_catalogue.html", context)


def add_product(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                'New product "{name}" added successfully!'.format(
                    name=form.cleaned_data["name"]
                ),
            )
            return redirect("add_product")

        else:
            messages.error(
                request, "Product not added, please correct the errors below!"
            )

    else:
        form = ProductForm()

    return render(request, "adminpanel/products/add_product.html", {"form": form})


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    editing = request.GET.get("edit") == "true"
    form = None

    if editing:
        if request.method == "POST":

            form = ProductForm(request.POST, request.FILES, instance=product)

            if form.is_valid():
                form.save()
                messages.success(
                    request,
                    'Product "{name}" updated successfully!'.format(
                        name=form.cleaned_data["name"]
                    ),
                )
                return redirect("product_detail", pk=product.pk)

            else:
                messages.error(
                    request, "Product not updated, please correct the errors below!"
                )

        else:
            form = ProductForm(instance=product)
            form.fields["stock"].disabled = True

    return render(
        request,
        "adminpanel/products/product_detail.html",
        {"product": product, "editing": editing, "form": form},
    )


def deactivate_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        product.is_active = False
        product.save()
        messages.success(
            request,
            'Product "{name}" deactivated successfully!'.format(name=product.name),
        )
        return redirect("product_detail", pk=product.pk)
    return redirect("product_detail", pk=product.pk)


def activate_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        product.is_active = True
        product.save()
        messages.success(
            request,
            'Product "{name}" activated successfully!'.format(name=product.name),
        )
        return redirect("product_detail", pk=product.pk)
    return redirect("product_detail", pk=product.pk)


def restock(request):
    products = Product.objects.filter(is_active=True)
    products_to_restock = products.filter(stock__lt=F("reorder_threshold"))
    products_to_restock = products_to_restock.annotate(
        restock_ratio=ExpressionWrapper(
            F("stock") * 1.0 / F("reorder_threshold"), output_field=FloatField()
        )
    )
    main_categories = Category.objects.filter(parent__isnull=True)
    selected_categories = [
        c for c in request.GET.getlist("category") if c.strip() != ""
    ]
    query = request.GET.get("q")
    sort = request.GET.get("sort")
    query_params = request.GET.copy()
    page = query_params.pop("page", [None])[0]
    query_string = query_params.urlencode()

    if query:
        products_to_restock = products_to_restock.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
        )

    if selected_categories:
        products_to_restock = products_to_restock.filter(
            Q(category_id__in=selected_categories)
            | Q(category__parent_id__in=selected_categories)
        )

    sort_fields = [
        "name",
        "-name",
        "stock",
        "-stock",
        "restock_ratio",
        "-restock_ratio",
    ]

    if sort in sort_fields:
        products_to_restock = products_to_restock.order_by(sort)

    paginator = Paginator(products_to_restock, 15)
    page_num = request.GET.get("page")
    page_obj = paginator.get_page(page_num)

    return render(
        request,
        "adminpanel/restock/restock_dashboard.html",
        {
            "products_to_restock": page_obj.object_list,
            "page_obj": page_obj,
            "main_categories": main_categories,
            "selected_categories": selected_categories,
            "query": query,
            "sort": sort,
            "query_string": query_string,
        },
    )


def add_stock_select(request):
    query = request.GET.get("q")
    products = Product.objects.filter(is_active=True)

    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    paginator = Paginator(products, 15)
    page_num = request.GET.get("page")
    page_obj = paginator.get_page(page_num)

    query_params = request.GET.copy()
    page = query_params.pop("page", [None])[0]
    query_string = query_params.urlencode()

    return render(
        request,
        "adminpanel/restock/add_stock_select.html",
        {
            "products": products,
            "query": query,
            "page_obj": page_obj,
            "query_string": query_string,
        },
    )


def add_stock(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        try:
            qty = int(request.POST.get("quantity", 0))
            if qty < 0:
                messages.error(request, "Quantity must be greater than 0.")
            else:
                product.stock += qty
                product.save()
                messages.success(
                    request,
                    'Successfully added {qty} units to "{name}"!'.format(
                        qty=qty, name=product.name
                    ),
                )
                return redirect("restock")
        except ValueError:
            messages.error(request, "Please enter a valid integer for added stock.")

    deficit = max(0, product.reorder_threshold - product.stock)

    return render(
        request,
        "adminpanel/restock/add_stock.html",
        {"product": product, "deficit": deficit},
    )


def customers(request):
    return render(request, "adminpanel/customers/customer_records.html")
