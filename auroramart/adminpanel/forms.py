from django import forms

from storefront.models import Category, Product, Customer


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "price",
            "category",
            "stock",
            "reorder_threshold",
            "description",
            "image",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "is_active": forms.CheckboxInput(),
            "image": forms.FileInput(),
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
    first_name = forms.CharField(max_length=150, required=False, label="First Name")
    last_name = forms.CharField(max_length=150, required=False, label="Last Name")
    email = forms.EmailField(required=True, label="Email Address")
    is_active = forms.BooleanField(
        required=False, initial=True, label="Account Active?"
    )
    deactivation_reason = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Reason for deactivating this account (will be shown to the customer)",
            }
        ),
        required=False,
        label="Deactivation Reason",
        help_text="This reason will be displayed to the customer when they try to log in.",
    )

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
        if self.instance and self.instance.pk and self.instance.user:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email
            self.fields["is_active"].initial = self.instance.user.is_active
            self.fields["deactivation_reason"].initial = (
                self.instance.user.deactivation_reason or ""
            )

        field_order = [
            "first_name",
            "last_name",
            "email",
            "is_active",
            "deactivation_reason",
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
        if customer.user:
            customer.user.first_name = self.cleaned_data.get("first_name", "")
            customer.user.last_name = self.cleaned_data.get("last_name", "")
            customer.user.email = self.cleaned_data.get("email", "")
            customer.user.is_active = self.cleaned_data.get("is_active", True)

            if not customer.user.is_active:
                customer.user.deactivation_reason = self.cleaned_data.get(
                    "deactivation_reason", ""
                )
            else:
                customer.user.deactivation_reason = None

            if commit:
                customer.user.save()
        if commit:
            customer.save()
        return customer
