from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.products, name='products'),
    path('restock/', views.restock, name='restock'),
    path('customers/', views.customers, name='customers'),
]