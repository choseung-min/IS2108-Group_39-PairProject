from django.urls import path
from . import views
from django.http import HttpResponse
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", views.home, name="home2"),
    path("cart", views.cart_view, name="cart"),
    path("cart/guest/", views.cart_guest, name="cart_guest"),
    path("cart/add/<int:product_id>/", views.cart_add, name="cart_add"),
    path("cart/update/<int:item_id>/", views.cart_update, name="cart_update"),
    path("cart/remove/<int:item_id>/", views.cart_remove, name="cart_remove"),
    path("signup", views.signup, name="signup"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path(
        "account/deactivated",
        views.account_deactivated_view,
        name="account_deactivated",
    ),
    path("account/appeal/submit", views.submit_appeal_view, name="submit_appeal"),
    path("account", views.profile_view, name="account"),
    path("account/orders", views.orders_list_view, name="orders_list"),
    path(
        "account/orders/<int:order_id>/", views.order_detail_view, name="order_detail"
    ),
    path(
        "account/orders/<int:order_id>/reorder",
        views.reorder_order_view,
        name="order_reorder",
    ),
    path(
        "c/<slug:slug>/", views.home, name="category"
    ),  # Reuse home view for category filtering
    path("p/<slug:slug>/", views.product_detail, name="product"),
    path("checkout/address", views.checkout_address_view, name="checkout_address"),
    path("checkout/payment", views.checkout_payment_view, name="checkout_payment"),
    path(
        "order/success/<str:order_id>/", views.order_success_view, name="order_success"
    ),  # take note I am using order_id not order_number
    path(
        "password_reset/",
        auth_views.PasswordResetView.as_view(
            template_name="storefront/password_reset_form.html"
        ),
        name="password_reset",
    ),
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="storefront/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="storefront/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="storefront/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
