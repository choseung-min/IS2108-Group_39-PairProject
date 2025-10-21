from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, 'adminpanel/index.html')

def products(request):
    return render(request, 'adminpanel/products/product_catalogue.html')

def restock(request):
    return render(request, 'adminpanel/restock/restock_dashboard.html')

def customers(request):
    return render(request, 'adminpanel/customers/customer_records.html')