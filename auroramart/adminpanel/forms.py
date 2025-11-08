from django import forms

from storefront.models import Category, Product, Customer


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "description",
            "category",
            "stock",
            "reorder_threshold",
            "price",
            "image",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "is_active": forms.CheckboxInput(),
        }
        labels = {
            "sku": "SKU Code",
            "name": "Product Name",
            "stock": "Stock Quantity",
            "reorder_threshold": "Reorder Threshold",
            "price": "Price",
            "image": "Product Image",
            "is_active": "Active?",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.main_categories = Category.objects.filter(
            parent__isnull=True
        ).prefetch_related("category_set")
        self.fields["category"].queryset = Category.objects.all()


class CustomerForm(forms.ModelForm):
    # Add User model fields
    first_name = forms.CharField(max_length=150, required=False, label="First Name")
    last_name = forms.CharField(max_length=150, required=False, label="Last Name")
    email = forms.EmailField(required=True, label="Email Address")

    class Meta:
        model = Customer
        fields = [
            "phone",
            "age",
            "household_size",
            "has_children",
            "monthly_income",
            "gender",
            "employment_status",
            "occupation",
            "education",
            "address",
            "postal_code",
            "city_state",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "has_children": forms.CheckboxInput(),
        }
        labels = {
            "phone": "Phone Number",
            "age": "Age",
            "household_size": "Household Size",
            "has_children": "Has Children?",
            "monthly_income": "Monthly Income",
            "gender": "Gender",
            "employment_status": "Employment Status",
            "occupation": "Occupation",
            "education": "Education Level",
            "address": "Address",
            "postal_code": "Postal Code",
            "city_state": "City/State",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate initial values from the related User object
        if self.instance and self.instance.pk and self.instance.user:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email

        # Reorder fields so User fields come first
        field_order = [
            "first_name",
            "last_name",
            "email",  # User fields first
            "phone",
            "age",
            "household_size",
            "has_children",
            "monthly_income",
            "gender",
            "employment_status",
            "occupation",
            "education",
            "address",
            "postal_code",
            "city_state",
        ]
        self.order_fields(field_order)

    def save(self, commit=True):
        customer = super().save(commit=False)
        # Save the User fields
        if customer.user:
            customer.user.first_name = self.cleaned_data.get("first_name", "")
            customer.user.last_name = self.cleaned_data.get("last_name", "")
            customer.user.email = self.cleaned_data.get("email", "")
            if commit:
                customer.user.save()
        if commit:
            customer.save()
        return customer
