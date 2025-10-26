from django.urls import path
from . import views
from django.http import HttpResponse

urlpatterns = [
    path('', views.home, name='home'),
    path('cart', lambda request: HttpResponse("Cart page (coming soon)"), name='cart'),
    path('signup', lambda request: HttpResponse("Signup page (coming soon)"), name='signup'),
    path('login', lambda request: HttpResponse("Login page (coming soon)"), name='login'),
    path('logout', lambda request: HttpResponse("Logout page (coming soon)"), name='logout'),
    path('account', lambda request: HttpResponse("Account page (coming soon)"), name='account'),  # Placeholder
    path('c/<slug:slug>/', views.home, name='category'),  # Reuse home view for category filtering
    path('p/<slug:slug>/', lambda request, slug: HttpResponse(f"Product detail page for {slug} (coming soon)"), name='product'),
    path('card/add/<int:pk>/', lambda request, pk: HttpResponse(f"Add product {pk} to cart (coming soon)"), name='cart_add'),
]