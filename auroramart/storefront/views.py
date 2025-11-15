from decimal import Decimal
from typing import List, Tuple
from django.db import transaction
from django.db.models import Q
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.utils import timezone
from urllib.parse import urlencode
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.http import JsonResponse
from .forms import (
    UserSignupForm,
    CustomerForm,
    EmailLoginForm,
    AddressForm,
    PaymentForm,
    ProfileForm,
)
from .models import (
    Product,
    Category,
    Cart,
    CartItem,
    Customer,
    Order,
    OrderItem,
    Appeal,
    AppealDocument,
)

User = get_user_model()
from .ml.category_predictor import predict_preferred_category
import joblib
import os
from django.apps import apps

app_path = apps.get_app_config("storefront").path
model_path = os.path.join(
    app_path, "mlmodels", "b2c_products_500_transactions_50k.joblib"
)
loaded_rules = joblib.load(model_path)


# Create your views here.
# Association rules recommendation function
def get_recommendations(loaded_rules, items, metric="confidence", top_n=3):
    recommendations = set()

    for item in items:
        matched_rules = loaded_rules[
            loaded_rules["antecedents"].apply(lambda x: item in x)
        ]

        if len(matched_rules) > 0:
            if metric in loaded_rules.columns:
                top_rules = matched_rules.sort_values(by=metric, ascending=False).head(
                    top_n
                )

                for idx, row in top_rules.iterrows():
                    recommendations.update(row["consequents"])

    recommendations.difference_update(items)

    return list(recommendations)[:top_n]


# Home View
def home(request, slug=None):
    # Only show active products in storefront
    products = Product.objects.select_related("category").filter(is_active=True)

    # PARENTS ONLY (the 12 main categories)
    categories = Category.objects.filter(parent__isnull=True).order_by("name")[:12]

    q = (request.GET.get("q") or "").strip()
    sort = (request.GET.get("sort") or "").strip()

    category = None
    if slug:
        category = get_object_or_404(Category, slug=slug)
        products = products.filter(Q(category=category) | Q(category__parent=category))

    if q:
        products = products.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(category__name__icontains=q) |
            Q(category__parent__name__icontains=q)
        )

    if sort == "price_asc":
        products = products.order_by("price", "-rating", "name")
    elif sort == "price_desc":
        products = products.order_by("-price", "-rating", "name")
    elif sort == "new":
        products = products.order_by("-id")
    else:
        products = products.order_by("-rating", "name")

    context = {
        "categories": categories,
        "products": products[:500],
        "q": q,
        "sort": sort,
        "category": category,
    }
    return render(request, "storefront/home.html", context)


# Signup/Login/Logout Views
def preferred_category_url_for(user) -> str:
    customer = getattr(user, "customer", None)
    if not customer or not customer.preferred_category:
        return reverse("home2")

    label = customer.preferred_category.strip()

    cat = Category.objects.filter(name__iexact=label).first()
    if not cat:
        cat = Category.objects.filter(slug__iexact=label).first()

    if cat:
        return reverse("category", kwargs={"slug": cat.slug})
    return reverse("home2")


def signup(request):
    if request.method == "POST":
        uform = UserSignupForm(request.POST)
        cform = CustomerForm(request.POST)
        if uform.is_valid() and cform.is_valid():

            user = uform.save()
            customer = cform.save(user=user)

            # For category prediction
            try:
                payload = {
                    "age": customer.age,
                    "household_size": customer.household_size,
                    "has_children": 1 if customer.has_children else 0,
                    "monthly_income_sgd": customer.monthly_income or 0,
                    "gender": customer.gender,
                    "employment_status": customer.employment_status,
                    "occupation": customer.occupation,
                    "education": customer.education,
                }
                category_pred = predict_preferred_category(payload)
                if isinstance(category_pred, (list, tuple)) or hasattr(
                    category_pred, "__iter__"
                ):
                    category_pred = category_pred[0]
                category_str = str(category_pred).strip()

                customer.preferred_category = category_str
                customer.save(update_fields=["preferred_category"])
            except Exception as e:
                print("AI prediction error:", e)

            # Log in and send to Data Acknowledgement
            login(request, user)
            next_url = preferred_category_url_for(user)
            ack_url = f"{reverse('data_ack')}?{urlencode({'next': next_url})}"
            return redirect(ack_url)
    else:
        uform = UserSignupForm()
        cform = CustomerForm()

    return render(request, "storefront/signup.html", {"uform": uform, "cform": cform})


@login_required
def data_acknowledgement(request):
    next_url = request.GET.get("next") or request.POST.get("next") or reverse("account")

    if request.method == "POST":
        if request.POST.get("agree") == "on":
            return redirect(next_url)
        messages.error(request, "Please check the acknowledgement box to continue.")

    return render(request, "storefront/data_ack.html", {"next": next_url})


def login_view(request):
    if request.method == "POST":
        form = EmailLoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data.get("user")

            # Check if account is deactivated
            if user is None and "deactivated_email" in form.cleaned_data:
                request.session["deactivated_email"] = form.cleaned_data[
                    "deactivated_email"
                ]
                request.session["deactivation_reason"] = form.cleaned_data.get(
                    "deactivation_reason", ""
                )
                # Store user ID for appeal checking
                try:
                    deactivated_user = User.objects.get(
                        email__iexact=form.cleaned_data["deactivated_email"]
                    )
                    request.session["deactivated_user_id"] = deactivated_user.id
                except User.DoesNotExist:
                    pass
                return redirect("account_deactivated")

            login(request, user)

            # Check for 'next' parameter first (with security validation)
            next_url = request.GET.get("next") or request.POST.get("next")
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)

            # Check if user is admin/staff and redirect accordingly
            if user.is_staff or user.is_superuser:
                return redirect("/adminpanel/")  # Redirect to admin panel
            else:
                return redirect(
                    preferred_category_url_for(user)
                )  # Redirect to storefront
    else:
        form = EmailLoginForm()
    return render(request, "storefront/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("home2")


def account_deactivated_view(request):
    """Display page for deactivated accounts with appeal information"""
    email = request.session.get("deactivated_email", "")
    reason = request.session.get("deactivation_reason", "")
    user_id = request.session.get("deactivated_user_id", None)

    # Check for pending or declined appeals
    has_pending_appeal = False
    appeal_declined = False
    decline_reason = ""
    pending_appeal_date = None

    if user_id:
        try:
            user = User.objects.get(id=user_id)
            customer = Customer.objects.get(user=user)

            # Check for latest appeal
            latest_appeal = (
                Appeal.objects.filter(customer=customer).order_by("-created_at").first()
            )

            if latest_appeal:
                if latest_appeal.status == "pending":
                    has_pending_appeal = True
                    pending_appeal_date = latest_appeal.created_at
                elif latest_appeal.status == "declined":
                    appeal_declined = True
                    decline_reason = (
                        latest_appeal.decline_reason
                        or "Your appeal was reviewed and declined."
                    )
        except (User.DoesNotExist, Customer.DoesNotExist):
            pass

    # Clear the session data after retrieving it (except user_id for appeal submission)
    if "deactivated_email" in request.session:
        del request.session["deactivated_email"]
    if "deactivation_reason" in request.session:
        del request.session["deactivation_reason"]

    context = {
        "email": email,
        "reason": reason,
        "has_pending_appeal": has_pending_appeal,
        "appeal_declined": appeal_declined,
        "decline_reason": decline_reason,
        "pending_appeal_date": pending_appeal_date,
    }
    return render(request, "storefront/account_deactivated.html", context)


# Cart Views
def cart_guest(request):
    return render(request, "storefront/cart_guest.html")


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
            return redirect("login")

        qty = max(1, int(request.POST.get("quantity", "1") or 1))
        with transaction.atomic():
            cart = _get_cart_for(request.user)
            item, created = CartItem.objects.select_for_update().get_or_create(
                cart=cart,
                product=p,
                defaults={"quantity": qty, "price_snapshot": p.price},
            )
            if not created:
                item.quantity += qty
                if item.price_snapshot is None:
                    item.price_snapshot = p.price
            item.save(update_fields=["quantity", "price_snapshot"])

        request.session["cart_count"] = cart.count
        messages.success(request, f"Added {qty} × {p.name} to cart!")
        return redirect("product", slug=slug)

    fbt_products = []
    try:
        fbt_skus = (
            get_recommendations(
                loaded_rules,
                items=[p.sku],          
                metric="lift",    
                top_n=3
            ) or []
        )

        if fbt_skus:
            qs = (
                Product.objects.filter(
                    sku__in=fbt_skus,
                    is_active=True,
                    stock__gt=0,
                )
                .exclude(pk=p.pk)
            )
            product_map = {prod.sku: prod for prod in qs}
            fbt_products = [
                product_map[sku] for sku in fbt_skus if sku in product_map
            ]
    except Exception as e:
        print("FBT error:", e)
        fbt_products = []

    return render(request, "storefront/product_detail.html",
        {
            "product": p,
            "fbt_products": fbt_products,   # 0–3 items
        },
    )


@login_required
def cart_add(request, product_id):
    p = get_object_or_404(Product, pk=product_id, is_active=True)

    if request.method == "POST":
        quantity_str = request.POST.get("quantity", "").strip()
        if not quantity_str:
            referer = request.META.get("HTTP_REFERER", "")
            if "/cart/recommendations/" in referer:
                return redirect("cart_recommendations")
            return redirect("product", slug=p.slug)
        try:
            qty = max(1, int(quantity_str))
        except ValueError:
            messages.error(request, "Quantity must be a whole number.")
            return redirect("product", slug=p.slug)
    else:
        qty = 1

    cart = _get_cart_for(request.user)
    with transaction.atomic():
        item, created = CartItem.objects.select_for_update().get_or_create(
            cart=cart, product=p, defaults={"quantity": qty, "price_snapshot": p.price}
        )
        if not created:
            item.quantity += qty
            if item.price_snapshot is None:
                item.price_snapshot = p.price
            item.save(update_fields=["quantity", "price_snapshot"])

    request.session["cart_count"] = cart.count

    # 👇 NEW: go back to where the form told us
    next_url = request.POST.get("next")
    if next_url:
        messages.success(request, f"Added {qty} × {p.name} to cart!")
        return redirect(next_url)

    referer = request.META.get("HTTP_REFERER", "")
    if "/cart/recommendations/" in referer:
        return redirect("cart_recommendations")

    return redirect("cart")


def cart_view(request):
    if not request.user.is_authenticated:
        return render(request, "storefront/cart_guest.html")

    cart = _get_cart_for(request.user)
    items = cart.items.select_related("product").all()

    # Check for and remove deactivated products from cart
    deactivated_items = []
    for item in items:
        if not item.product.is_active:
            deactivated_items.append(item.product.name)
            item.delete()

    if deactivated_items:
        messages.warning(
            request,
            f"The following products have been removed from your cart as they are no longer available: {', '.join(deactivated_items)}",
        )
        # Refresh items after deletion
        items = cart.items.select_related("product").all()
        request.session["cart_count"] = cart.count

    return render(request, "storefront/cart.html", {"cart": cart, "items": items})


@login_required
def cart_update(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__customer__user=request.user)

    # Check if product is still active
    if not item.product.is_active:
        messages.error(
            request,
            f"{item.product.name} is no longer available and has been removed from your cart.",
        )
        cart = item.cart
        item.delete()
        request.session["cart_count"] = cart.count
        return redirect("cart")

    action = request.POST.get("action")
    if action == "inc":
        item.quantity += 1
        item.save(update_fields=["quantity"])
    elif action == "dec":
        item.quantity = max(1, item.quantity - 1)
        item.save(update_fields=["quantity"])
    request.session["cart_count"] = item.cart.count
    return redirect("cart")


@login_required
def cart_remove(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__customer__user=request.user)
    cart = item.cart
    item.delete()
    request.session["cart_count"] = cart.count
    return redirect("cart")


@login_required
def recommend_addons_view(request):
    cart = _get_cart_for(request.user)
    items = cart.items.select_related("product").all()

    if not items:
        return redirect("checkout_address")

    skus = [ci.product.sku for ci in items]
    suggested_products = []

    try:
        suggested_skus = (
            get_recommendations(loaded_rules, skus, metric="confidence", top_n=3) or []
        )

        if suggested_skus:
            product_map = {
                p.sku: p for p in Product.objects.filter(sku__in=suggested_skus)
            }
            suggested_products = [
                product_map[sku] for sku in suggested_skus if sku in product_map
            ]
    except Exception:
        suggested_products = []

    return render(
        request,
        "storefront/cart_recommendations.html",
        {
            "cart": cart,
            "items": items,
            "suggested_products": suggested_products,  
        },
    )


# checkout views
SESSION_KEY = "checkout"


def _reprice_and_check_stock(cart_items) -> Tuple[bool, List[str], list, Decimal]:
    ok, errs, priced = True, [], []
    subtotal = Decimal("0.00")

    # Pull product inline, avoid repeated queries
    for ci in cart_items.select_related("product"):
        p, q = ci.product, ci.quantity

        # Check if product is still active
        if not p.is_active:
            ok = False
            errs.append(f"{p.name}: This product is no longer available.")
            continue

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
        return redirect("cart")

    customer = request.user.customer

    initial = {
        "address": getattr(customer, "address", "") or "",
        "city_state": getattr(customer, "city_state", "") or "",
        "postal_code": getattr(customer, "postal_code", "") or "",
    }

    if sess := request.session.get(SESSION_KEY):
        initial.update(
            {
                "address": sess.get("address", initial["address"]),
                "city_state": sess.get("city_state", initial["city_state"]),
                "postal_code": sess.get("postal_code", initial["postal_code"]),
            }
        )

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

            return redirect("checkout_payment")
        messages.error(request, "Please fix the address fields.")
    else:
        form = AddressForm(initial=initial)

    ok, errs, priced, subtotal = _reprice_and_check_stock(items)
    shipping_fee = Decimal("0.00")
    tax = Decimal("0.00")
    total = subtotal + shipping_fee + tax

    context = {
        "form": form,
        "cart_items": items.select_related("product"),
        "subtotal": subtotal,
        "shipping_fee": shipping_fee,
        "tax": tax,
        "total": total,
    }
    return render(request, "storefront/checkout_address.html", context)


@login_required
@transaction.atomic
def checkout_payment_view(request):
    sess = request.session.get(SESSION_KEY)
    if not sess:
        messages.warning(
            request, "Please provide a delivery address before proceeding to payment."
        )
        return redirect("checkout_address")

    cart = _get_cart_for(request.user)
    items = CartItem.objects.filter(cart=cart)
    if not items.exists():
        messages.info(request, "Your cart is empty. Add items before checking out.")
        return redirect("cart")

    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            # Reprice and stock check
            ok, errs, priced, subtotal = _reprice_and_check_stock(items)
            if not ok:
                for e in errs:
                    messages.error(request, e)
                return redirect("checkout_address")

            shipping_fee = Decimal("0.00")
            tax = Decimal("0.00")
            total = subtotal + shipping_fee + tax

            delivery_address_text = _compose_delivery_address(
                sess["address"], sess.get("city_state", ""), sess["postal_code"]
            )

            # Create Order
            order = Order.objects.create(
                customer=request.user.customer,
                status=f"Pending ({form.cleaned_data['payment_method']})",
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
                ci.product.save(update_fields=["stock"])

            # Clear cart
            items.delete()
            request.session.pop(SESSION_KEY, None)

            return redirect("order_success", order_id=order.id)
        messages.error(request, "Please select a valid payment method.")
    else:
        form = PaymentForm()

    ok, errs, priced, subtotal = _reprice_and_check_stock(items)
    shipping_fee = Decimal("0.00")
    tax = Decimal("0.00")
    total = subtotal + shipping_fee + tax

    addr_preview = _compose_delivery_address(
        sess["address"], sess.get("city_state", ""), sess["postal_code"]
    )

    context = {
        "form": form,
        "addr_text": addr_preview,
        "cart_items": items.select_related("product"),
        "subtotal": subtotal,
        "shipping_fee": shipping_fee,
        "tax": tax,
        "total": total,
    }
    return render(request, "storefront/checkout_payment.html", context)


@login_required
def order_success_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer__user=request.user)
    return render(request, "storefront/order_success.html", {"order": order})


# view profile views
@login_required
def profile_view(request):
    customer = request.user.customer

    if request.method == "POST":
        form = ProfileForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            try:
                payload = {
                    "age": customer.age,
                    "household_size": customer.household_size,
                    "has_children": 1 if customer.has_children else 0,
                    "monthly_income_sgd": customer.monthly_income or 0,
                    "gender": customer.gender,
                    "employment_status": customer.employment_status,
                    "occupation": customer.occupation,
                    "education": customer.education,
                }

                category_pred = predict_preferred_category(payload)
                if isinstance(category_pred, (list, tuple)) or hasattr(
                    category_pred, "__iter__"
                ):
                    category_pred = category_pred[0]
                category_str = str(category_pred).strip()

                customer.preferred_category = category_str
                customer.save(update_fields=["preferred_category"])

                messages.success(request, f"Profile updated successfully.")
            except Exception as e:
                print("AI prediction error (profile update):", e)
                messages.warning(
                    request,
                    "Profile updated, but personalisation could not be refreshed at this time.",
                )

            return redirect("account")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ProfileForm(request.user)

    orders = Order.objects.filter(customer=customer).order_by("-order_date")[:5]
    return render(request, "storefront/account.html", {"form": form, "orders": orders})


@login_required
def orders_list_view(request):
    orders = Order.objects.filter(customer=request.user.customer).order_by(
        "-order_date"
    )
    return render(request, "storefront/orders_list.html", {"orders": orders})


@login_required
def order_detail_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user.customer)
    items = OrderItem.objects.filter(order=order).select_related("product")

    context = {
        "order": order,
        "items": items,
    }

    return render(request, "storefront/order_detail.html", context)


@login_required
@login_required
def order_mark_received(request, order_id):
    # Only allow POST
    if request.method != "POST":
        return redirect("order_detail2", order_id=order_id)

    order = get_object_or_404(Order, pk=order_id, customer__user=request.user)

    # Set to your "completed" value. If you use choices/consts, replace accordingly.
    completed_value = "Order Completed"  # e.g., Order.STATUS_COMPLETED if you have it
    order.status = completed_value
    order.save(update_fields=["status"])

    return redirect("order_detail2", order_id=order.id)


@login_required
@transaction.atomic
def reorder_order_view(request, order_id):
    """Add all items from a previous order back into the cart."""
    order = get_object_or_404(Order, id=order_id, customer=request.user.customer)
    cart = _get_cart_for(request.user)

    skipped_products = []
    added_count = 0

    for oi in OrderItem.objects.filter(order=order).select_related("product"):
        # Skip deactivated products
        if not oi.product.is_active:
            skipped_products.append(oi.product.name)
            continue

        ci, created = CartItem.objects.get_or_create(
            cart=cart,
            product=oi.product,
            defaults={"quantity": oi.quantity, "price_snapshot": oi.price_at_purchase},
        )
        if not created:
            ci.quantity += oi.quantity
            if ci.price_snapshot is None:
                ci.price_snapshot = oi.price_at_purchase
            ci.save(update_fields=["quantity", "price_snapshot"])
        added_count += 1

    # Notify user about skipped products
    if skipped_products:
        messages.warning(
            request,
            f"The following product(s) have been deactivated and were not added to your cart: {', '.join(skipped_products)}",
        )

    if added_count > 0:
        messages.success(request, f"{added_count} item(s) successfully added to your cart.")
    elif skipped_products:
        # All products were deactivated
        messages.error(
            request,
            "Unable to reorder: All products from this order have been deactivated."
        )
    else:
        # No items in the order (edge case)
        messages.info(request, "This order has no items to reorder.")

    request.session["cart_count"] = cart.count
    return redirect("cart")


@transaction.atomic
def submit_appeal_view(request):
    """Handle appeal submission from deactivated customers"""
    if request.method != "POST":
        return redirect("login")

    appeal_statement = request.POST.get("appeal_statement", "").strip()
    user_id = request.session.get("deactivated_user_id")

    if not appeal_statement:
        messages.error(request, "Please provide an appeal statement.")
        return redirect("account_deactivated")

    if not user_id:
        messages.error(request, "Session expired. Please log in again.")
        return redirect("login")

    try:
        # Find the user and customer from session
        user = User.objects.get(id=user_id)
        customer = Customer.objects.get(user=user)

        # Check if user is actually deactivated
        if user.is_active:
            messages.error(request, "This account is not deactivated.")
            return redirect("login")

        # Check if there's already a pending appeal
        existing_pending = Appeal.objects.filter(
            customer=customer, status="pending"
        ).exists()

        if existing_pending:
            messages.warning(
                request,
                "You already have a pending appeal. Please wait for it to be reviewed.",
            )
            return redirect("account_deactivated")

        # Create the appeal
        appeal = Appeal.objects.create(
            customer=customer, appeal_statement=appeal_statement, status="pending"
        )

        # Handle multiple file uploads
        files = request.FILES.getlist("documents")
        for file in files:
            if file:
                AppealDocument.objects.create(appeal=appeal, document=file)

        messages.success(
            request,
            "Your appeal has been submitted successfully and is pending review by our admin team.",
        )

        # Session already has the user_id, no need to reset

    except User.DoesNotExist:
        messages.error(request, "User account not found. Please log in again.")
        return redirect("login")
    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found.")
    except Exception as e:
        messages.error(
            request,
            f"An error occurred while submitting your appeal. Please try again.",
        )

    return redirect("account_deactivated")
