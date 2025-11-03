from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.products, name='products'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/add', views.add_product, name='add_product'),
    path('products/<int:pk>/activate/', views.activate_product, name='activate_product'),
    path('products/<int:pk>/deactivate/', views.deactivate_product, name='deactivate_product'),
    path('restock/', views.restock, name='restock'),
    path('customers/', views.customers, name='customers'),
]