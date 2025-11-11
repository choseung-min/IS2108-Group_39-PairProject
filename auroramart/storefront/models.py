from django.db import models
from django.utils.text import slugify
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from decimal import Decimal


# Create your models here.
class User(AbstractUser):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("customer", "Customer"),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="customer")
    deactivation_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for account deactivation (shown to user)",
    )

    def save(self, *args, **kwargs):
        # auto-set admin role when creating a superuser
        if self.is_superuser:
            self.role = "admin"
        # Clear deactivation reason if account is reactivated
        if self.is_active and self.deactivation_reason:
            self.deactivation_reason = None
        super().save(*args, **kwargs)


class Customer(models.Model):

    HOUSEHOLD_SIZE = (
        (1, "1"),
        (2, "2"),
        (3, "3"),
        (4, "4"),
        (5, "5"),
    )

    GENDER_CHOICES = (
        ("Male", "Male"),
        ("Female", "Female"),
    )

    EMPLOYMENT_STATUS = (
        ("Full-time", "Full-time"),
        ("Part-time", "Part-time"),
        ("Student", "Student"),
        ("Self-employed", "Self-employed"),
        ("Retired", "Retired"),
    )

    OCCUPATION_CHOICES = (
        ("Sales", "Sales"),
        ("Service", "Service"),
        ("Admin", "Admin"),
        ("Tech", "Tech"),
        ("Education", "Education"),
        ("Skilled Trades", "Skilled Trades"),
    )

    EDUCATION_CHOICES = (
        ("Diploma", "Diploma"),
        ("Bachelor", "Bachelor"),
        ("Secondary", "Secondary"),
        ("Master", "Master"),
        ("Doctorate", "Doctorate"),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    age = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(18), MaxValueValidator(120)]
    )
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
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        # A category name should be unique within the same parent level
        unique_together = [["name", "parent"]]

    def __str__(self):
        return self.name


class Product(models.Model):

    sku = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey("Category", on_delete=models.CASCADE)

    # inventory & merchandising
    stock = models.PositiveIntegerField(default=0)
    reorder_threshold = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)

    # price & review
    price = models.DecimalField(max_digits=10, decimal_places=2)
    rating = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)], default=0.0
    )
    image = models.ImageField(upload_to="product_images/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Cart(models.Model):
    customer = models.OneToOneField(
        "Customer", on_delete=models.CASCADE, related_name="cart"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total(self):
        return sum(
            (item.line_total for item in self.items.select_related("product")),
            Decimal("0.00"),
        )

    @property
    def count(self) -> int:
        return sum(item.quantity for item in self.items.all())

    def __str__(self):
        return f"Cart of {self.customer.user.get_full_name() or self.customer.user.username}"


class CartItem(models.Model):
    cart = models.ForeignKey("Cart", on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("Product", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price_snapshot = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    class Meta:
        unique_together = ("cart", "product")

    @property
    def line_total(self) -> Decimal:
        return self.price_snapshot * self.quantity

    def __str__(self):
        return f"{self.quantity} of {self.product.name} in {self.cart.customer.user.get_full_name() or self.cart.customer.user.username}'s cart"


class Order(models.Model):
    customer = models.ForeignKey("Customer", on_delete=models.CASCADE)
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default="Pending")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_address = models.CharField(max_length=255)

    def __str__(self):
        return f"Order {self.id} by {self.customer.user.get_full_name() or self.customer.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey("Order", on_delete=models.CASCADE)
    product = models.ForeignKey("Product", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self) -> Decimal:
        return self.price_at_purchase * self.quantity

    def __str__(self):
        return f"{self.quantity} of {self.product.name} in Order {self.order.id}"
