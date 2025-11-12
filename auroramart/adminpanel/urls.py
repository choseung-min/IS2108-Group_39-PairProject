from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.products, name="products"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
    path("products/add", views.add_product, name="add_product"),
    path(
        "products/<int:pk>/activate/", views.activate_product, name="activate_product"
    ),
    path(
        "products/<int:pk>/deactivate/",
        views.deactivate_product,
        name="deactivate_product",
    ),
    path("restock/", views.restock, name="restock"),
    path("restock/add", views.add_stock_select, name="add_stock_select"),
    path("restock/add/<int:pk>/", views.add_stock, name="add_stock"),
    path("customers/", views.customers, name="customers"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path(
        "customers/<int:pk>/activate/",
        views.activate_customer,
        name="activate_customer",
    ),
    path(
        "customers/<int:pk>/deactivate/",
        views.deactivate_customer,
        name="deactivate_customer",
    ),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("appeals/", views.appeals_list, name="appeals_list"),
    path("appeals/<int:pk>/", views.appeal_detail, name="appeal_detail"),
    path("appeals/<int:pk>/approve/", views.approve_appeal, name="approve_appeal"),
    path("appeals/<int:pk>/decline/", views.decline_appeal, name="decline_appeal"),
    path("logout/", views.logout_view, name="admin_logout"),
]
