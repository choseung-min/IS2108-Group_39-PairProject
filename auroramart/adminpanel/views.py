from urllib import request
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from storefront.models import Product, Category, Customer, Order, OrderItem
from django.db.models import Q, F, ExpressionWrapper, FloatField
from django.core.paginator import Paginator
from .forms import ProductForm, CustomerForm


def is_admin_or_staff(user):
    """Check if user is authenticated and is either staff or admin"""
    return user.is_authenticated and (
        user.is_staff or user.is_superuser or user.role == "admin"
    )


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
def home(request):
    return render(request, "adminpanel/home_page.html")


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
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


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
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


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    editing = request.GET.get("edit") == "true"
    form = None

    if editing:
        if request.method == "POST":
            form = ProductForm(request.POST, request.FILES, instance=product)
            # Disable stock field and preserve its value
            form.fields["stock"].disabled = True
            # Remove is_active field from edit form
            form.fields.pop("is_active", None)

            if form.is_valid():
                # Preserve the original stock value since it's disabled
                updated_product = form.save(commit=False)
                updated_product.stock = product.stock
                updated_product.save()

                messages.success(
                    request,
                    'Product "{name}" updated successfully!'.format(
                        name=form.cleaned_data["name"]
                    ),
                )
                # Redirect with updated=true to show preview link
                return redirect(
                    f"{reverse('product_detail', kwargs={'pk': product.pk})}?updated=true"
                )

            else:
                messages.error(
                    request, "Product not updated, please correct the errors below!"
                )

        else:
            form = ProductForm(instance=product)
            form.fields["stock"].disabled = True
            # Remove is_active field from edit form
            form.fields.pop("is_active", None)

    # Check if product was just updated
    just_updated = request.GET.get("updated") == "true"

    return render(
        request,
        "adminpanel/products/product_detail.html",
        {
            "product": product,
            "editing": editing,
            "form": form,
            "just_updated": just_updated,
        },
    )


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
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


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
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


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
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
    query_params.pop("page", None)
    query_params.pop("sort", None)
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


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
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


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
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


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
def customers(request):
    customers = Customer.objects.all()
    query = request.GET.get("q")
    status_filter = request.GET.get("status_filter")
    sort = request.GET.get("sort")

    query_params = request.GET.copy()
    page = query_params.pop("page", [None])[0]
    query_string = query_params.urlencode()

    if query:
        customers = customers.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
        )

    if status_filter:
        if status_filter == "active":
            customers = customers.filter(user__is_active=True)
        elif status_filter == "inactive":
            customers = customers.filter(user__is_active=False)

    sort_fields = [
        "user__first_name",
        "-user__first_name",
        "user__date_joined",
        "-user__date_joined",
    ]

    if sort in sort_fields:
        customers = customers.order_by(sort)
    else:
        # Default ordering to avoid pagination warning
        customers = customers.order_by("user__first_name", "user__last_name")

    paginator = Paginator(customers, 15)
    page_num = request.GET.get("page")
    page_obj = paginator.get_page(page_num)

    context = {
        "page_obj": page_obj,
        "customers": page_obj.object_list,
        "query": query,
        "sort": sort,
        "query_string": query_string,
        "status_filter": status_filter,
    }

    return render(request, "adminpanel/customers/customer_records.html", context)


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
def customer_detail(request, pk):
    customer = get_object_or_404(Customer.objects.select_related("user"), pk=pk)
    editing = request.GET.get("edit") == "true"
    form = None

    # Get all orders for this customer
    orders = customer.order_set.all().order_by("-order_date")

    if editing:
        if request.method == "POST":
            form = CustomerForm(request.POST, instance=customer)
            # Remove is_active and deactivation_reason from editable fields
            form.fields.pop("is_active", None)
            form.fields.pop("deactivation_reason", None)

            if form.is_valid():
                form.save()
                messages.success(
                    request,
                    'Customer "{name}" updated successfully!'.format(
                        name=customer.user.get_full_name() or customer.user.username
                    ),
                )
                return redirect("customer_detail", pk=customer.pk)
            else:
                messages.error(
                    request, "Customer not updated, please correct the errors below!"
                )
        else:
            form = CustomerForm(instance=customer)
            # Remove is_active and deactivation_reason from editable fields
            form.fields.pop("is_active", None)
            form.fields.pop("deactivation_reason", None)

    return render(
        request,
        "adminpanel/customers/customer_detail.html",
        {"customer": customer, "editing": editing, "form": form, "orders": orders},
    )


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
def deactivate_customer(request, pk):
    customer = get_object_or_404(Customer.objects.select_related("user"), pk=pk)

    if request.method == "POST":
        deactivation_reason = request.POST.get("deactivation_reason", "").strip()

        if not deactivation_reason:
            messages.error(
                request, "Please provide a reason for deactivating the account."
            )
            return redirect("customer_detail", pk=customer.pk)

        customer.user.is_active = False
        customer.user.deactivation_reason = deactivation_reason
        customer.user.save()
        messages.success(
            request,
            'Customer "{name}" deactivated successfully!'.format(
                name=customer.user.get_full_name() or customer.user.username
            ),
        )
        return redirect("customer_detail", pk=customer.pk)
    return redirect("customer_detail", pk=customer.pk)


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
def activate_customer(request, pk):
    customer = get_object_or_404(Customer.objects.select_related("user"), pk=pk)

    if request.method == "POST":
        customer.user.is_active = True
        customer.user.deactivation_reason = None  # Clear the deactivation reason
        customer.user.save()
        messages.success(
            request,
            'Customer "{name}" activated successfully!'.format(
                name=customer.user.get_full_name() or customer.user.username
            ),
        )
        return redirect("customer_detail", pk=customer.pk)
    return redirect("customer_detail", pk=customer.pk)


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("customer", "customer__user").prefetch_related(
            "orderitem_set__product"
        ),
        pk=pk,
    )
    order_items = order.orderitem_set.all()

    return render(
        request,
        "adminpanel/orders/order_detail.html",
        {"order": order, "order_items": order_items},
    )


def logout_view(request):
    logout(request)
    return redirect("home2")  # Redirect to storefront home
