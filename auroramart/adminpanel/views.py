from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from storefront.models import (
    Product,
    Category,
    Customer,
    Order,
    OrderItem,
    Appeal,
    AppealDocument,
)
from django.db.models import (
    Q,
    F,
    ExpressionWrapper,
    FloatField,
    Case,
    When,
    Value,
    IntegerField,
)
from django.db.models.functions import Concat
from django.core.paginator import Paginator
from .forms import ProductForm, CustomerForm


def is_admin_or_staff(user):
    """Check if user is authenticated and is either staff or admin"""
    return user.is_authenticated and (user.is_superuser or user.role == "admin")


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
def home(request):
    from datetime import timedelta
    from django.db.models import Sum
    from django.utils import timezone

    total_products = Product.objects.count()
    active_products = Product.objects.filter(is_active=True).count()
    inactive_products = Product.objects.filter(is_active=False).count()
    low_stock_products = Product.objects.filter(
        is_active=True, stock__lt=F("reorder_threshold")
    ).count()
    out_of_stock_products = Product.objects.filter(stock=0).count()

    products_needing_restock = Product.objects.filter(
        is_active=True, stock__lt=F("reorder_threshold")
    )
    total_restock_count = products_needing_restock.count()
    products_with_ratio = products_needing_restock.annotate(
        restock_ratio=ExpressionWrapper(
            F("stock") * 1.0 / F("reorder_threshold"), output_field=FloatField()
        )
    )
    critical_restock_count = products_with_ratio.filter(restock_ratio__lte=0.25).count()

    total_customers = Customer.objects.count()
    active_customers = Customer.objects.filter(user__is_active=True).count()
    inactive_customers = Customer.objects.filter(user__is_active=False).count()

    pending_appeals_count = Appeal.objects.filter(status="pending").count()
    total_appeals = Appeal.objects.count()

    seven_days_ago = timezone.now() - timedelta(days=7)

    top_products = (
        OrderItem.objects.filter(order__order_date__gte=seven_days_ago)
        .values("product__name", "product__id")
        .annotate(total_quantity=Sum("quantity"))
        .order_by("-total_quantity")[:10]
    )

    top_categories = (
        OrderItem.objects.filter(order__order_date__gte=seven_days_ago)
        .values("product__category__name")
        .annotate(total_quantity=Sum("quantity"))
        .order_by("-total_quantity")[:10]
    )

    recent_orders = Order.objects.select_related("customer__user").order_by(
        "-order_date"
    )[:10]

    context = {
        "total_products": total_products,
        "active_products": active_products,
        "inactive_products": inactive_products,
        "low_stock_products": total_restock_count,  # For sidebar badge
        "out_of_stock_products": out_of_stock_products,
        "total_restock_count": total_restock_count,
        "critical_restock_count": critical_restock_count,
        "total_customers": total_customers,
        "active_customers": active_customers,
        "inactive_customers": inactive_customers,
        "pending_appeals_count": pending_appeals_count,
        "total_appeals": total_appeals,
        "top_products": top_products,
        "top_categories": top_categories,
        "recent_orders": recent_orders,
    }
    return render(request, "adminpanel/home_page.html", context)


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

    paginator = Paginator(products, 12)
    page_num = request.GET.get("page")
    page_obj = paginator.get_page(page_num)

    low_stock_count = Product.objects.filter(
        is_active=True, stock__lt=F("reorder_threshold")
    ).count()

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
            form.fields["stock"].disabled = True
            form.fields.pop("is_active", None)

            if form.is_valid():

                updated_product = form.save(commit=False)
                updated_product.stock = product.stock
                updated_product.save()

                return redirect(
                    reverse(
                        "product_detail",
                        kwargs={"pk": product.pk},
                        query={"updated": "true"},
                    )
                )

            else:
                messages.error(
                    request, "Product not updated, please correct the errors below!"
                )

        else:
            form = ProductForm(instance=product)
            form.fields["stock"].disabled = True
            form.fields.pop("is_active", None)

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

    total_restock_count = products_to_restock.count()

    critical_count = products_to_restock.filter(restock_ratio__lte=0.25).count()
    high_count = products_to_restock.filter(
        restock_ratio__gt=0.25, restock_ratio__lte=0.5
    ).count()
    medium_count = products_to_restock.filter(
        restock_ratio__gt=0.5, restock_ratio__lte=0.75
    ).count()
    low_count = products_to_restock.filter(restock_ratio__gt=0.75).count()

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
            | Q(sku__icontains=query)
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

    paginator = Paginator(products_to_restock, 12)
    page_num = request.GET.get("page")
    page_obj = paginator.get_page(page_num)

    context = {
        "products_to_restock": page_obj.object_list,
        "page_obj": page_obj,
        "main_categories": main_categories,
        "selected_categories": selected_categories,
        "query": query,
        "sort": sort,
        "query_string": query_string,
        "critical_count": critical_count,
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "total_restock_count": total_restock_count,
    }

    return render(
        request,
        "adminpanel/restock/restock_dashboard.html",
        context,
    )


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
def add_stock_select(request):
    query = request.GET.get("q")
    products = Product.objects.filter(is_active=True)

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(category__name__icontains=query)
            | Q(description__icontains=query)
            | Q(sku__icontains=query)
        )

    paginator = Paginator(products, 12)
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
        customers = customers.annotate(
            full_name=Concat("user__first_name", Value(" "), "user__last_name")
        ).filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(full_name__icontains=query)
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

    paginator = Paginator(customers, 12)
    page_num = request.GET.get("page")
    page_obj = paginator.get_page(page_num)

    pending_appeals_count = Appeal.objects.filter(status="pending").count()

    context = {
        "page_obj": page_obj,
        "customers": page_obj.object_list,
        "query": query,
        "sort": sort,
        "query_string": query_string,
        "status_filter": status_filter,
        "pending_appeals_count": pending_appeals_count,
    }

    return render(request, "adminpanel/customers/customer_records.html", context)


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
def customer_detail(request, pk):
    customer = get_object_or_404(Customer.objects.select_related("user"), pk=pk)
    editing = request.GET.get("edit") == "true"
    form = None

    orders = customer.order_set.all().order_by("-order_date")

    if editing:
        if request.method == "POST":
            form = CustomerForm(request.POST, instance=customer)
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
    customer.user.save(update_fields=["is_active", "deactivation_reason"])
    Appeal.objects.filter(customer=customer, status="declined").update(
        decline_reason=None
    )
    messages.success(
        request,
        'Customer "{name}" deactivated successfully! Reason: {reason}'.format(
            name=customer.user.get_full_name() or customer.user.username,
            reason=deactivation_reason,
        ),
    )
    return redirect("customer_detail", pk=customer.pk)


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
def activate_customer(request, pk):
    customer = get_object_or_404(Customer.objects.select_related("user"), pk=pk)

    if request.method == "POST":
        customer.user.is_active = True
        customer.user.deactivation_reason = None
        customer.user.save()

        Appeal.objects.filter(customer=customer).delete()
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
    return redirect("home2")


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
def appeals_list(request):
    appeals = Appeal.objects.select_related("customer__user").all()
    query = request.GET.get("q")
    status_filter = request.GET.get("status_filter")
    sort = request.GET.get("sort")

    query_params = request.GET.copy()
    page = query_params.pop("page", [None])[0]
    query_string = query_params.urlencode()

    if query:
        appeals = appeals.filter(
            Q(customer__user__first_name__icontains=query)
            | Q(customer__user__last_name__icontains=query)
            | Q(customer__user__email__icontains=query)
            | Q(appeal_statement__icontains=query)
        )

    if status_filter:
        appeals = appeals.filter(status=status_filter)

    appeals = appeals.annotate(
        priority=Case(
            When(status="pending", then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
    ).order_by("priority", "-created_at")

    paginator = Paginator(appeals, 12)
    page_num = request.GET.get("page")
    page_obj = paginator.get_page(page_num)

    pending_count = Appeal.objects.filter(status="pending").count()

    context = {
        "page_obj": page_obj,
        "appeals": page_obj.object_list,
        "query": query,
        "status_filter": status_filter,
        "sort": sort,
        "query_string": query_string,
        "pending_count": pending_count,
    }

    return render(request, "adminpanel/appeals/appeals_list.html", context)


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
def appeal_detail(request, pk):
    appeal = get_object_or_404(
        Appeal.objects.select_related("customer__user", "reviewed_by"), pk=pk
    )
    documents = AppealDocument.objects.filter(appeal=appeal).order_by("uploaded_at")

    context = {
        "appeal": appeal,
        "documents": documents,
    }

    return render(request, "adminpanel/appeals/appeal_detail.html", context)


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
@transaction.atomic
def approve_appeal(request, pk):
    if request.method != "POST":
        return redirect("appeal_detail", pk=pk)

    appeal = get_object_or_404(Appeal, pk=pk)

    if appeal.status != "pending":
        messages.error(request, "This appeal has already been reviewed.")
        return redirect("appeal_detail", pk=pk)

    appeal.status = "approved"
    appeal.reviewed_at = timezone.now()
    appeal.reviewed_by = request.user
    appeal.save()

    customer_user = appeal.customer.user
    customer_user.is_active = True
    customer_user.deactivation_reason = None
    customer_user.save()

    Appeal.objects.filter(customer=appeal.customer, status="declined").update(
        decline_reason=None
    )

    messages.success(
        request,
        f"Appeal approved successfully. Customer account for {customer_user.get_full_name() or customer_user.username} has been reactivated.",
    )

    return redirect("appeal_detail", pk=pk)


@login_required(login_url="/login")
@user_passes_test(is_admin_or_staff, login_url="/login")
@transaction.atomic
def decline_appeal(request, pk):
    if request.method != "POST":
        return redirect("appeal_detail", pk=pk)

    appeal = get_object_or_404(Appeal, pk=pk)

    if appeal.status != "pending":
        messages.error(request, "This appeal has already been reviewed.")
        return redirect("appeal_detail", pk=pk)

    decline_reason = request.POST.get("decline_reason", "").strip()

    if not decline_reason:
        messages.error(request, "Please provide a reason for declining the appeal.")
        return redirect("appeal_detail", pk=pk)

    appeal.status = "declined"
    appeal.reviewed_at = timezone.now()
    appeal.reviewed_by = request.user
    appeal.decline_reason = decline_reason
    appeal.save()

    messages.success(
        request,
        f"Appeal declined successfully.",
    )

    return redirect("appeal_detail", pk=pk)
