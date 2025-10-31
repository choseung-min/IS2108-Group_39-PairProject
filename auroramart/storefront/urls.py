from django.urls import path
from . import views
from django.http import HttpResponse

urlpatterns = [
    path('', views.home, name='home'),
    path('cart', views.cart_view, name='cart'),
    path('cart/guest/', views.cart_guest, name='cart_guest'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:item_id>/', views.cart_update, name='cart_update'),
    path('cart/remove/<int:item_id>/', views.cart_remove, name='cart_remove'),
    path('signup', views.signup, name='signup'),
    path('login', views.login_view, name='login'),
    path('logout', views.logout_view, name='logout'),
    path('account', lambda request: HttpResponse("Account page (coming soon)"), name='account'),
    path('c/<slug:slug>/', views.home, name='category'),  # Reuse home view for category filtering
    path('p/<slug:slug>/', views.product_detail, name='product'),
]