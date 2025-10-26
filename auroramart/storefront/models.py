from django.db import models
from django.utils.text import slugify
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator

# Create your models here.
class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('customer', 'Customer'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')

class Customer(models.Model):

    HOUSEHOLD_SIZE = (
        (1, '1'),
        (2, '2'),
        (3, '3'),
        (4, '4'),
        (5, '5'),
    )

    GENDER_CHOICES = (
        ('Male', 'Male'),
        ('Female', 'Female'),
    )

    EMPLOYMENT_STATUS = (
        ('Full-time', 'Full-time'),
        ('Part-time', 'Part-time'),
        ('Student', 'Student'),
        ('Self-employed', 'Self-employed'),
        ('Retired', 'Retired'),
    )

    OCCUPATION_CHOICES = (
        ('Sales', 'Sales'),
        ('Service', 'Service'),
        ('Admin', 'Admin'),
        ('Tech', 'Tech'),
        ('Education', 'Education'),
        ('Skilled Trades', 'Skilled Trades'),
    )

    EDUCATION_CHOICES = (
        ('Diploma', 'Diploma'),
        ('Bachelor', 'Bachelor'),
        ('Secondary', 'Secondary'),
        ('Master', 'Master'),
        ('Doctorate', 'Doctorate'),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    age = models.PositiveSmallIntegerField(validators=[MinValueValidator(18), MaxValueValidator(120)])
    household_size = models.IntegerField(choices=HOUSEHOLD_SIZE)
    has_children = models.BooleanField(default=False)
    monthly_income = models.DecimalField(max_digits=10, decimal_places=2)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    employment_status = models.CharField(max_length=15, choices=EMPLOYMENT_STATUS)
    occupation = models.CharField(max_length=100, choices=OCCUPATION_CHOICES)
    education = models.CharField(max_length=20, choices=EDUCATION_CHOICES)
    address = models.TextField()
    postal_code = models.CharField(max_length=10)
    city_state = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return self.user.username

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name
    
class Product(models.Model):
    
    sku = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey('Category', on_delete=models.CASCADE)

    #inventory & merchandising
    stock = models.PositiveIntegerField(default=0)
    reorder_threshold = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)

    #price & review
    price = models.DecimalField(max_digits=10, decimal_places=2)
    rating = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(5.0)], default=0.0)
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Cart(models.Model):
    customer = models.OneToOneField('Customer', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart of {self.customer.name}"
    
class CartItem(models.Model):
    cart = models.ForeignKey('Cart', on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} of {self.product.name} in {self.cart.customer.name}'s cart"

class Order(models.Model):
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE)
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default='Pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_address = models.CharField(max_length=255)

    def __str__(self):
        return f"Order {self.id} by {self.customer.name}"
    
class OrderItem(models.Model):
    order = models.ForeignKey('Order', on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} of {self.product.name} in Order {self.order.id}"